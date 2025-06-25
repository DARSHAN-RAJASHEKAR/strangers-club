# app/api/endpoints/auth.py
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import httpx
from typing import Dict, Any
from jose import jwt
import secrets
import hashlib
import base64

from app.db.base import get_db
from app.auth.oauth import oauth, create_access_token, get_current_user
from app.crud.user import get_or_create_user_by_google_info
from app.crud.invitation import verify_invitation_code, use_invitation
from app.crud.group import add_user_to_group, get_group, add_new_user_to_general_groups
from app.schemas.user import Token, User
from app.schemas.invitation import InvitationVerify
from app.config import settings

router = APIRouter()

# In-memory state storage for OAuth (production should use Redis)
oauth_states = {}

logger = logging.getLogger(__name__)

def generate_state():
    """Generate a cryptographically secure state parameter"""
    return secrets.token_urlsafe(32)

def store_state(state: str, expires_in: int = 600):
    """Store state with expiration (10 minutes)"""
    import time
    oauth_states[state] = time.time() + expires_in
    
def verify_state(state: str) -> bool:
    """Verify state and clean up expired states"""
    import time
    current_time = time.time()
    
    # Clean up expired states
    expired_keys = [k for k, v in oauth_states.items() if v < current_time]
    for key in expired_keys:
        del oauth_states[key]
    
    # Check if state exists and is valid
    if state in oauth_states and oauth_states[state] > current_time:
        del oauth_states[state]  # One-time use
        return True
    return False

@router.get("/login/google")
async def login_google(request: Request):
    """
    Redirect to Google OAuth login page with improved state management.
    """
    try:
        # Generate and store state
        state = generate_state()
        store_state(state)
        
        # Build authorization URL manually for better control
        google_auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "state": state
        }
        
        # Build URL
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{google_auth_url}?{query_string}"
        
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        print(f"Error in login_google: {e}")
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=auth_init_failed")

@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Handle Google OAuth callback with robust error handling.
    """
    try:
        # Check for OAuth errors
        if error:
            print(f"OAuth error: {error}")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=oauth_denied")
        
        if not code:
            print("No authorization code received")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=no_code")
        
        if not state:
            print("No state parameter received")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=no_state")
        
        # Verify state parameter
        if not verify_state(state):
            print(f"State verification failed: {state}")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=state_mismatch")
        
        # Exchange authorization code for tokens
        token_data = await exchange_code_for_tokens(code)
        if not token_data:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=token_exchange_failed")
        
        # Get user info
        user_info = await get_google_user_info(token_data.get("access_token"))
        if not user_info:
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=user_info_failed")
        
        # Get or create user
        user = await get_or_create_user_by_google_info(db, {
            "id": user_info.get("sub"),
            "email": user_info.get("email")
        })
        
        # Check if the user needs to complete registration (invitation verification)
        if not user.is_superuser and len(user.invitations_received) == 0:
            temp_token = create_access_token(
                data={"sub": user.email},
                expires_delta=timedelta(minutes=30)
            )
            redirect_url = f"{settings.FRONTEND_URL}/invite?token={temp_token}"
            return RedirectResponse(url=redirect_url)
        
        # Create access token for authenticated user
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        # Check if user needs phone verification
        if not user.phone_verified:
            logger.info(f"User {user.email} needs phone verification")
            redirect_url = f"{settings.FRONTEND_URL}/verify-phone?token={access_token}"
            return RedirectResponse(url=redirect_url)
        
        # If already verified, go to app
        redirect_url = f"{settings.FRONTEND_URL}/app?token={access_token}"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        print(f"Error in google_callback: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=callback_error")

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access tokens.
    """
    try:
        token_endpoint = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_endpoint, data=data)
            
            if response.status_code != 200:
                print(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
                
            return response.json()
            
    except Exception as e:
        print(f"Error in token exchange: {e}")
        return None

async def get_google_user_info(access_token: str) -> Dict[str, Any]:
    """
    Get user information from Google using access token.
    """
    try:
        userinfo_endpoint = "https://www.googleapis.com/oauth2/v3/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(userinfo_endpoint, headers=headers)
            
            if response.status_code != 200:
                print(f"User info failed: {response.status_code} - {response.text}")
                return None
                
            return response.json()
            
    except Exception as e:
        print(f"Error getting user info: {e}")
        return None

@router.post("/verify-invitation", response_model=Token)
async def verify_invitation(
    invitation_in: InvitationVerify,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Verify an invitation code and complete user registration.
    """
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = auth_header.split(" ")[1]
        
        # Validate token and get user
        try:
            user = await get_current_user(token=token, db=db)
            logger.info(f"User {user.email} attempting to verify invitation")
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Validate invitation code input
        if not invitation_in.code or len(invitation_in.code.strip()) == 0:
            logger.warning("Empty invitation code provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation code is required"
            )
        
        # Clean and validate the code
        clean_code = invitation_in.code.strip().upper()
        logger.info(f"Verifying invitation code: {clean_code}")
        
        # Verify invitation code
        invitation = await verify_invitation_code(db, clean_code)
        if not invitation:
            logger.warning(f"Invalid invitation code: {clean_code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired invitation code"
            )
        
        logger.info(f"Valid invitation found: {invitation.id}")
        
        # Use the invitation
        try:
            invitation = await use_invitation(db, invitation.id, user.id)
            logger.info(f"Invitation {invitation.id} marked as used by user {user.id}")
        except Exception as e:
            logger.error(f"Failed to mark invitation as used: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process invitation"
            )
        
        # Add user to the specific group
        try:
            await add_user_to_group(db, invitation.group_id, user.id)
            logger.info(f"User {user.id} added to group {invitation.group_id}")
        except Exception as e:
            logger.error(f"Failed to add user to group: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to join group"
            )
        
        # Add user to ALL general groups
        try:
            await add_new_user_to_general_groups(db, user.id)
            logger.info(f"User {user.id} added to general groups")
        except Exception as e:
            logger.error(f"Failed to add user to general groups: {e}")
            # This is not critical, so we'll log but not fail
        
        # Create a new access token for the fully registered user
        try:
            access_token = create_access_token(
                data={"sub": user.email},
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            logger.info(f"New access token created for user {user.email}")
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create access token"
            )
        
        # Always set requires_phone_verification to True if not already verified
        requires_phone_verification = not user.phone_verified
        
        # Log whether phone verification is required
        if requires_phone_verification:
            logger.info(f"User {user.email} needs phone verification after invitation verification")
        else:
            logger.info(f"User {user.email} already has verified phone, skipping verification")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "requires_phone_verification": requires_phone_verification
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in verify_invitation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred"
        )

@router.post("/join-group", response_model=Dict[str, str])
async def join_group_with_code(
    invitation_in: InvitationVerify,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Join a group using an invitation code (for already registered users).
    """
    # Verify invitation code
    invitation = await verify_invitation_code(db, invitation_in.code)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation code"
        )
    
    # Check if user is already a member of the group
    group = await get_group(db, invitation.group_id)
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    member_ids = [member.id for member in group.members]
    if current_user.id in member_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this group"
        )
    
    # Add user to the group
    await add_user_to_group(db, invitation.group_id, current_user.id)
    
    return {
        "message": f"Successfully joined group: {group.name}",
        "group_id": str(group.id),
        "group_name": group.name
    }

@router.get("/me", response_model=User)
async def read_users_me(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user information.
    """
    return current_user
import os
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import httpx
from typing import Dict, Any
from jose import jwt

from app.db.base import get_db
from app.auth.oauth import oauth, create_access_token, get_current_user
from app.crud.user import get_or_create_user_by_google_info
from app.crud.invitation import verify_invitation_code, use_invitation
from app.crud.group import add_user_to_group, get_group, add_new_user_to_general_groups
from app.schemas.user import Token, User
from app.schemas.invitation import InvitationVerify
from app.config import settings

router = APIRouter()

@router.get("/login/google")
async def login_google(request: Request):
    """
    Redirect to Google OAuth login page.
    """
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str = None,
    state: str = None,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Handle Google OAuth callback with workaround for state mismatch issue.
    """
    try:
        # Try the standard OAuth flow
        token = await oauth.google.authorize_access_token(request)
        resp = await oauth.google.parse_id_token(request, token)
        
        user = await get_or_create_user_by_google_info(db, {
            "id": resp.get("sub"),
            "email": resp.get("email")
        })
        
        # Check if the user is NOT a superuser AND has no invitations
        if not user.is_superuser and not user.invitations_received:
            temp_token = create_access_token(
                data={"sub": user.email},
                expires_delta=timedelta(minutes=30)
            )
            redirect_url = f"{settings.FRONTEND_URL}/invite?token={temp_token}"
            return RedirectResponse(url=redirect_url)
        
        # Admin users or users with invitations will proceed here
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        redirect_url = f"{settings.FRONTEND_URL}/app?token={access_token}"
        return RedirectResponse(url=redirect_url)
    
    except Exception as e:
        # If there's a state mismatch or other error, try the manual approach
        if code:
            try:
                # Manually exchange the authorization code for tokens
                token_endpoint = "https://oauth2.googleapis.com/token"
                data = {
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code"
                }
                
                async with httpx.AsyncClient() as client:
                    resp = await client.post(token_endpoint, data=data)
                    token_data = resp.json()
                
                if "error" in token_data:
                    return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=token_error")
                
                # Get user info using userinfo endpoint
                access_token_google = token_data.get("access_token")
                if not access_token_google:
                    return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=no_access_token")
                
                userinfo_endpoint = "https://www.googleapis.com/oauth2/v3/userinfo"
                async with httpx.AsyncClient() as client:
                    userinfo_resp = await client.get(
                        userinfo_endpoint,
                        headers={"Authorization": f"Bearer {access_token_google}"}
                    )
                    user_info = userinfo_resp.json()
                
                if "error" in user_info or "sub" not in user_info:
                    return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=userinfo_error")
                
                # Get or create user
                user = await get_or_create_user_by_google_info(db, {
                    "id": user_info.get("sub"),
                    "email": user_info.get("email")
                })
                
                # Check if the user is NOT a superuser AND has no invitations
                if not user.is_superuser and not user.invitations_received:
                    temp_token = create_access_token(
                        data={"sub": user.email},
                        expires_delta=timedelta(minutes=30)
                    )
                    redirect_url = f"{settings.FRONTEND_URL}/invite?token={temp_token}"
                    return RedirectResponse(url=redirect_url)
                
                # Admin users or users with invitations will proceed here
                access_token = create_access_token(
                    data={"sub": user.email},
                    expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
                )
                
                redirect_url = f"{settings.FRONTEND_URL}/app?token={access_token}"
                return RedirectResponse(url=redirect_url)
                
            except Exception as manual_error:
                import traceback
                traceback.print_exc()
                return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=authentication_failed")
        
        # If no authorization code or other issue
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=authentication_failed")

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
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split(" ")[1]
    
    # Validate token and get user
    try:
        user = await get_current_user(token=token, db=db)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify invitation code
    invitation = await verify_invitation_code(db, invitation_in.code)
    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invitation code"
        )
    
    # Use the invitation
    invitation = await use_invitation(db, invitation.id, user.id)
    
    # Add user to the specific group
    await add_user_to_group(db, invitation.group_id, user.id)
    
    # Add user to ALL general groups (improved logic)
    await add_new_user_to_general_groups(db, user.id)
    
    # Create a new access token for the fully registered user
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

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
    
    # Note: We don't mark the invitation as used for group invites
    # This allows the same code to be used multiple times
    
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
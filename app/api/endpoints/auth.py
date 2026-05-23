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
from app.crud import phone_verification as crud_phone
from app.schemas.user import Token, User
from app.schemas.invitation import InvitationVerify
from app.config import settings
from app.services.whatsapp import whatsapp_service
from datetime import datetime
from pydantic import BaseModel

class OtpRequest(BaseModel):
    phone: str   # "+91XXXXXXXXXX"

class OtpVerify(BaseModel):
    phone: str   # "+91XXXXXXXXXX"
    code: str

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
            request.session["token"] = temp_token
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/invite", status_code=302)
        
        # Create access token for authenticated user
        access_token = create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        # Store token in session (not in URL)
        request.session["token"] = access_token
        
        # Check if user needs phone verification (skip for admin/superuser)
        if not user.phone_verified and not user.is_superuser:
            logger.info(f"User {user.email} needs phone verification")
            return RedirectResponse(url=f"{settings.FRONTEND_URL}/verify-phone", status_code=302)
        
        # If already verified (or admin), go to app
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/app", status_code=302)
        
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

        # Sandbox: demo users can only use demo invite codes; real users cannot use demo codes
        is_demo_lounge = invitation.group and invitation.group.name == "Demo Lounge"
        inviter_is_demo = invitation.inviter and invitation.inviter.email.endswith("@demo.strangers.club")
        current_is_demo = user.email.endswith("@demo.strangers.club")
        if current_is_demo and not inviter_is_demo and not is_demo_lounge:
            raise HTTPException(status_code=403, detail="Demo accounts can only use demo invite codes.")
        if not current_is_demo and (inviter_is_demo or is_demo_lounge):
            raise HTTPException(status_code=403, detail="This invite code is for demo accounts only.")

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

        # Add real users to general groups (never demo users; excludes Demo Lounge)
        if not current_is_demo:
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
        
        # Skip phone verification for admin/superuser
        requires_phone_verification = not user.phone_verified and not user.is_superuser
        
        # Log whether phone verification is required
        if requires_phone_verification:
            logger.info(f"User {user.email} needs phone verification after invitation verification")
        else:
            logger.info(f"User {user.email} skipping phone verification (verified or admin)")
        
        # Update session with the new token (so subsequent page loads use the fresh token)
        request.session["token"] = access_token
        
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
    return current_user


@router.delete("/account")
async def delete_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete the current user's account — cleans all FK dependencies first (PostgreSQL safe)."""
    from sqlalchemy import text

    uid = str(current_user.id)

    # 1. Restore the invitation they used (so inviter gets it back)
    await db.execute(
        text("UPDATE invitations SET is_used=false, invitee_id=NULL, used_at=NULL WHERE invitee_id=:uid"),
        {"uid": uid}
    )

    # 2. Delete messages they authored
    await db.execute(text("DELETE FROM messages WHERE author_id=:uid"), {"uid": uid})

    # 3. Delete invitations they sent
    await db.execute(text("DELETE FROM invitations WHERE inviter_id=:uid"), {"uid": uid})

    # 4. Delete groups they own (cascade: messages → channels → invitations → memberships → group)
    result = await db.execute(text("SELECT id FROM groups WHERE owner_id=:uid"), {"uid": uid})
    owned_group_ids = [str(row[0]) for row in result.fetchall()]
    for gid in owned_group_ids:
        await db.execute(text("DELETE FROM messages WHERE channel_id IN (SELECT id FROM channels WHERE group_id=:gid)"), {"gid": gid})
        await db.execute(text("DELETE FROM channels WHERE group_id=:gid"), {"gid": gid})
        await db.execute(text("DELETE FROM invitations WHERE group_id=:gid"), {"gid": gid})
        await db.execute(text("DELETE FROM user_group WHERE group_id=:gid"), {"gid": gid})
        await db.execute(text("DELETE FROM groups WHERE id=:gid"), {"gid": gid})

    # 5. Remove from all group memberships
    await db.execute(text("DELETE FROM user_group WHERE user_id=:uid"), {"uid": uid})

    # 6. Delete phone verifications
    await db.execute(text("DELETE FROM phone_verifications WHERE user_id=:uid"), {"uid": uid})

    # 7. Delete the user (raw SQL to avoid ORM relationship cascade conflicts)
    await db.execute(text("DELETE FROM users WHERE id=:uid"), {"uid": uid})
    await db.commit()

    request.session.clear()
    return {"message": "Account deleted"}


@router.post("/demo")
async def demo_login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Create a fresh DEMO{N} user and return a token."""
    from sqlalchemy.future import select as sa_select
    from app.models.user import User as UserModel
    from app.models.group import Group
    from app.models.user import user_group as user_group_table
    from sqlalchemy import insert

    # Find the next available DEMO number (1–999) — check all DEMO* usernames
    result = await db.execute(
        sa_select(UserModel).where(UserModel.username.like("DEMO%"))
    )
    existing = result.scalars().all()
    used_nums = set()
    for u in existing:
        try:
            used_nums.add(int(u.username[4:]))
        except ValueError:
            pass
    next_num = next((n for n in range(1, 1000) if n not in used_nums), 1)

    demo_user = UserModel(
        email=f"demo{next_num}@demo.strangers.club",
        username=f"DEMO{next_num}",
        is_active=True,
        is_superuser=False,
        phone_verified=False,
    )
    db.add(demo_user)
    await db.commit()
    await db.refresh(demo_user)

    # Generate a real invite code for the Demo Lounge — always use "DEMO1" as prefix
    # so the code is always "DEMO1-XXX" = 8 chars in the grid (DEMO1XXX without dash)
    invite_code = None
    lounge = (await db.execute(
        sa_select(Group).where(Group.name == "Demo Lounge")
    )).scalars().first()
    if lounge:
        import random, string
        from app.models.invitation import Invitation as InvitationModel
        from datetime import timezone as tz
        # Keep generating until we get a unique code
        from app.crud.invitation import get_invitation_by_code
        for _ in range(10):
            letter = random.choice(string.ascii_uppercase)
            digits = f"{random.randint(10, 99)}"
            code = f"DEMO1-{letter}{digits}"
            if not await get_invitation_by_code(db, code):
                break
        inv = InvitationModel(
            code=code,
            inviter_id=demo_user.id,
            group_id=lounge.id,
            is_used=False,
            expires_at=datetime.now(tz.utc) + timedelta(days=7),
        )
        db.add(inv)
        await db.commit()
        invite_code = code  # always "DEMO1-XXX"

    # Generate a unique demo phone: 00000 + 5 random digits (never a real number)
    demo_phone = "00000" + f"{random.randint(10000, 99999)}"

    token = create_access_token(
        data={"sub": demo_user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    request.session["token"] = token
    return {"token": token, "invite_code": invite_code, "demo_phone": demo_phone}


@router.post("/demo-verify-phone")
async def demo_verify_phone(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Skip phone verification for demo users — marks phone_verified without sending OTP."""
    if not current_user.email.endswith("@demo.strangers.club"):
        raise HTTPException(status_code=403, detail="Demo accounts only")

    from sqlalchemy.future import select as sa_select
    from app.models.user import User as UserModel

    result = await db.execute(sa_select(UserModel).where(UserModel.id == current_user.id))
    user = result.scalars().first()
    user.phone_verified = True
    await db.commit()

    token = create_access_token(
        data={"sub": current_user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    request.session["token"] = token
    return {"token": token, "redirect": "/app"}


@router.post("/send-otp")
async def send_otp(
    body: OtpRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send WhatsApp OTP — used by new verify-phone UI."""
    # Strip country code prefix, keep 10 digits
    phone_number = body.phone.replace("+91", "").replace(" ", "").strip()
    if len(phone_number) != 10 or not phone_number.isdigit():
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit Indian mobile number")

    existing = await crud_phone.get_user_by_phone(db, phone_number)
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=400, detail="Phone number already registered to another account")

    await crud_phone.invalidate_previous_verifications(db, current_user.id, phone_number)
    verification = await crud_phone.create_verification(db, current_user.id, phone_number, 10)

    success = await whatsapp_service.send_otp(phone_number=phone_number, otp_code=verification.verification_code)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send OTP. Please try again.")

    return {"message": "Code sent", "expires_in": 600}


@router.post("/verify-otp")
async def verify_otp(
    body: OtpVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Verify WhatsApp OTP — used by new verify-phone UI."""
    phone_number = body.phone.replace("+91", "").replace(" ", "").strip()

    ok = await crud_phone.verify_code(db, current_user.id, phone_number, body.code)
    if not ok:
        raise HTTPException(status_code=400, detail="Code didn't match or has expired")

    access_token = create_access_token(
        data={"sub": current_user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    request.session["token"] = access_token
    return {"token": access_token, "redirect": "/app"}
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import logging

from app.db.base import get_db
from app.auth.oauth import get_current_active_user
from app.crud import invitation as crud_invitation
from app.crud import group as crud_group
from app.schemas.invitation import Invitation, InvitationCreate, InvitationUpdate, InvitationVerify
from app.schemas.user import User

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("", response_model=List[Invitation])
async def read_invitations(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all invitations created by the current user.
    """
    try:
        invitations = await crud_invitation.get_invitations_by_inviter(
            db, current_user.id, skip=skip, limit=limit
        )
        return invitations
    except Exception as e:
        logger.error(f"Error fetching invitations for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch invitations"
        )

@router.post("", response_model=Invitation)
async def create_invitation(
    invitation_in: InvitationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new invitation for a group.
    Special handling for platform invitations - any user can create invitations for general groups.
    Only group owners can create invitations for Timeleft meet-up groups.
    """
    try:
        # Check if the group exists
        group = await crud_group.get_group(db, invitation_in.group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Special case: For general groups (platform invitations), any registered user can create invitations
        if group.is_general:
            logger.info(f"User {current_user.id} creating platform invitation for general group {group.id}")
            invitation = await crud_invitation.create_invitation(
                db, invitation_in, inviter_id=current_user.id
            )
            return invitation
        
        # For Timeleft meet-up groups, only the group owner can create invitations
        if group.owner_id != current_user.id:
            raise HTTPException(
                status_code=403, 
                detail="Only the group owner can create invitations for Timeleft meet-up groups"
            )
        
        # Create the invitation
        invitation = await crud_invitation.create_invitation(
            db, invitation_in, inviter_id=current_user.id
        )
        
        logger.info(f"User {current_user.id} created invitation {invitation.id} for group {invitation_in.group_id}")
        return invitation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create invitation"
        )

@router.get("/by-group/{group_id}", response_model=List[Invitation])
async def read_group_invitations(
    group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all invitations for a specific group.
    """
    try:
        # Check if the group exists
        group = await crud_group.get_group(db, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # For general groups, any user can view invitations
        if group.is_general:
            invitations = await crud_invitation.get_invitations_by_group(
                db, group_id, skip=skip, limit=limit
            )
            return invitations
        
        # For Timeleft meet-up groups, only the group owner can view all invitations
        if group.owner_id != current_user.id:
            raise HTTPException(
                status_code=403, 
                detail="Only the group owner can view all invitations for this group"
            )
        
        # Get invitations for the group
        invitations = await crud_invitation.get_invitations_by_group(
            db, group_id, skip=skip, limit=limit
        )
        return invitations
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching group invitations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch group invitations"
        )

def normalize_code(code: str) -> str:
    """Insert dash at position 5 if user typed 8 chars without it (e.g. KQ317G34 → KQ317-G34)."""
    code = code.strip().upper().replace("-", "")
    if len(code) == 8:
        return code[:5] + "-" + code[5:]
    return code


@router.get("/verify/{code}")
async def verify_invitation_code(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """Preview invitation — public, no auth. Used to show 'invited by' and 'valid until' on the ticket stub."""
    code = normalize_code(code)
    invitation = await crud_invitation.verify_invitation_code(db, code)
    if not invitation:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation code")

    return {
        "valid": True,
        "inviter_username": invitation.inviter.username if invitation.inviter else "—",
        "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
        "group_name": invitation.group.name if invitation.group else "—",
    }


@router.post("/verify-code")
async def submit_invitation_code(
    invitation_in: InvitationVerify,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Use an invitation code — verifies, marks used, adds user to group, returns JWT."""
    from app.crud.group import add_user_to_group, add_new_user_to_general_groups
    from app.auth.oauth import create_access_token
    from app.config import settings
    from datetime import timedelta

    code = normalize_code(invitation_in.code)
    invitation = await crud_invitation.verify_invitation_code(db, code)
    if not invitation:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation code")

    # Sandbox: demo users can only join demo groups; real users can't join demo groups
    is_demo_lounge = invitation.group and invitation.group.name == "Demo Lounge"
    inviter_is_demo = invitation.inviter and invitation.inviter.email.endswith("@demo.strangers.club")
    current_is_demo = current_user.email.endswith("@demo.strangers.club")
    if current_is_demo and not inviter_is_demo and not is_demo_lounge:
        raise HTTPException(status_code=403, detail="Demo accounts can only use demo invite codes.")
    if not current_is_demo and (inviter_is_demo or is_demo_lounge):
        raise HTTPException(status_code=403, detail="This invite code is for demo accounts only.")

    invitation = await crud_invitation.use_invitation(db, invitation.id, current_user.id)
    await add_user_to_group(db, invitation.group_id, current_user.id)
    if not current_user.email.endswith("@demo.strangers.club"):
        await add_new_user_to_general_groups(db, current_user.id)

    token = create_access_token(
        data={"sub": current_user.email},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    request.session["token"] = token

    requires_phone = not current_user.phone_verified and not current_user.is_superuser
    return {
        "token": token,
        "redirect": "/verify-phone" if requires_phone else "/app",
    }


@router.get("/{invitation_id}", response_model=Invitation)
async def read_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific invitation by ID.
    """
    try:
        invitation = await crud_invitation.get_invitation(db, invitation_id)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        # Check if user is the inviter
        if invitation.inviter_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        return invitation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching invitation {invitation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch invitation"
        )

@router.delete("/{invitation_id}", response_model=Invitation)
async def delete_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete an invitation.
    """
    try:
        invitation = await crud_invitation.get_invitation(db, invitation_id)
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")

        # Check if user is the inviter or the group owner
        group = await crud_group.get_group(db, invitation.group_id)
        is_inviter = invitation.inviter_id == current_user.id
        is_group_owner = group and group.owner_id == current_user.id

        if not (is_inviter or is_group_owner):
            raise HTTPException(
                status_code=403,
                detail="Only the invitation creator or group owner can delete invitations"
            )

        # Check if invitation is already used
        if invitation.is_used:
            raise HTTPException(status_code=400, detail="Cannot delete a used invitation")

        invitation = await crud_invitation.delete_invitation(db, invitation_id=invitation_id)
        return invitation

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting invitation {invitation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete invitation"
        )

@router.post("/generate-new-code/{group_id}", response_model=Invitation)
async def generate_new_invitation_code(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a new invitation code for a group.
    For general groups (platform invitations), any user can generate codes.
    For Timeleft meet-up groups, only group owners can generate codes.
    """
    try:
        # Check if the group exists
        group = await crud_group.get_group(db, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Special case: For general groups (platform invitations), any registered user can generate codes
        if group.is_general:
            logger.info(f"User {current_user.id} generating platform invitation code for general group {group_id}")
            invitation_in = InvitationCreate(group_id=group_id)
            invitation = await crud_invitation.create_invitation(
                db, invitation_in, inviter_id=current_user.id
            )
            return invitation
        
        # For Timeleft meet-up groups, only the group owner can generate invitation codes
        if group.owner_id != current_user.id:
            raise HTTPException(
                status_code=403, 
                detail="Only the group owner can generate invitation codes for Timeleft meet-up groups"
            )
        
        # Create the invitation
        invitation_in = InvitationCreate(group_id=group_id)
        invitation = await crud_invitation.create_invitation(
            db, invitation_in, inviter_id=current_user.id
        )
        
        logger.info(f"User {current_user.id} generated new invitation code for group {group_id}")
        return invitation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating invitation code for group {group_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate invitation code"
        )

@router.post("/generate-platform-code", response_model=Invitation)
async def generate_platform_invite_code(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a platform invitation code for any registered user.
    Automatically finds or creates a general group — no group ID needed from the frontend.
    """
    from sqlalchemy.future import select as sa_select
    from app.models.group import Group
    from app.models.channel import Channel, ChannelType

    try:
        # Find an existing general group
        result = await db.execute(sa_select(Group).where(Group.is_general == True))
        general_group = result.scalars().first()

        # If none exists, create one owned by the current user
        if not general_group:
            logger.info(f"No general group found — creating one for user {current_user.id}")
            general_group = Group(
                name="General",
                description="Platform-wide general discussion group",
                is_general=True,
                owner_id=current_user.id
            )
            db.add(general_group)
            await db.commit()
            await db.refresh(general_group)

            default_channel = Channel(
                name="general",
                description="General discussion",
                type=ChannelType.GENERAL,
                group_id=general_group.id
            )
            db.add(default_channel)
            await db.commit()
            logger.info(f"Created default general group {general_group.id}")

        # Generate the invitation
        invitation_in = InvitationCreate(group_id=general_group.id)
        invitation = await crud_invitation.create_invitation(
            db, invitation_in, inviter_id=current_user.id
        )
        logger.info(f"Platform invite code generated by user {current_user.id}: {invitation.code}")
        return invitation

    except Exception as e:
        logger.error(f"Error generating platform invite code: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate platform invitation code"
        )
from fastapi import APIRouter, Depends, HTTPException, status
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

@router.get("/verify/{code}")
async def verify_invitation_code(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify if an invitation code is valid (public endpoint, no auth required).
    """
    try:
        logger.info(f"Verifying invitation code: {code}")
        
        # Validate code format
        if not code or len(code.strip()) == 0:
            logger.warning("Empty invitation code provided")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invitation code is required"
            )
        
        # Clean the code
        code = code.strip().upper()
        
        invitation = await crud_invitation.verify_invitation_code(db, code)
        if not invitation:
            logger.warning(f"Invalid invitation code: {code}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid or expired invitation code"
            )
        
        logger.info(f"Valid invitation code: {code}")
        
        # Return basic information about the invitation
        return {
            "valid": True,
            "group_name": invitation.group.name if invitation.group else "Unknown Group",
            "inviter_username": invitation.inviter.username if invitation.inviter else "Unknown User"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying invitation code {code}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify invitation code"
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
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.db.base import get_db
from app.auth.oauth import get_current_active_user
from app.crud import invitation as crud_invitation
from app.crud import group as crud_group
from app.schemas.invitation import Invitation, InvitationCreate, InvitationUpdate, InvitationVerify
from app.schemas.user import User

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
    invitations = await crud_invitation.get_invitations_by_inviter(
        db, current_user.id, skip=skip, limit=limit
    )
    return invitations

@router.post("", response_model=Invitation)
async def create_invitation(
    invitation_in: InvitationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new invitation for a group.
    """
    # Check if user is a member of the group
    group = await crud_group.get_group(db, invitation_in.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is the owner of the group
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can create invitations")
    
    invitation = await crud_invitation.create_invitation(
        db, invitation_in, inviter_id=current_user.id
    )
    return invitation

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
    # Check if user is a member of the group
    group = await crud_group.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is the owner of the group
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can view all invitations")
    
    invitations = await crud_invitation.get_invitations_by_group(
        db, group_id, skip=skip, limit=limit
    )
    return invitations

@router.get("/{invitation_id}", response_model=Invitation)
async def read_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific invitation by ID.
    """
    invitation = await crud_invitation.get_invitation(db, invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    # Check if user is the inviter
    if invitation.inviter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return invitation

@router.delete("/{invitation_id}", response_model=Invitation)
async def delete_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete an invitation.
    """
    invitation = await crud_invitation.get_invitation(db, invitation_id)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    
    # Check if user is the inviter
    if invitation.inviter_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the creator can delete the invitation")
    
    # Check if invitation is already used
    if invitation.is_used:
        raise HTTPException(status_code=400, detail="Cannot delete a used invitation")
    
    invitation = await crud_invitation.delete_invitation(db, invitation_id=invitation_id)
    return invitation

@router.get("/verify/{code}")
async def verify_invitation_code(
    code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify if an invitation code is valid (public endpoint, no auth required).
    """
    invitation = await crud_invitation.verify_invitation_code(db, code)
    if not invitation:
        raise HTTPException(status_code=400, detail="Invalid or expired invitation code")
    
    # Return basic information about the invitation
    return {
        "valid": True,
        "group_name": invitation.group.name,
        "inviter_username": invitation.inviter.username
    }

@router.post("/generate-new-code/{group_id}", response_model=Invitation)
async def generate_new_invitation_code(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Generate a new invitation code for a group.
    """
    # Check if user is a member of the group
    group = await crud_group.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if user is the owner of the group
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can generate invitation codes")
    
    invitation_in = InvitationCreate(group_id=group_id)
    invitation = await crud_invitation.create_invitation(
        db, invitation_in, inviter_id=current_user.id
    )
    return invitation
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from app.models.invitation import Invitation
from app.models.user import User
from app.schemas.invitation import InvitationCreate, InvitationUpdate
import logging

logger = logging.getLogger(__name__)

async def get_invitation(db: AsyncSession, invitation_id: UUID) -> Optional[Invitation]:
    """
    Get an invitation by ID.
    """
    result = await db.execute(
        select(Invitation).where(Invitation.id == invitation_id)
    )
    return result.scalars().first()

async def get_invitation_by_code(db: AsyncSession, code: str) -> Optional[Invitation]:
    """
    Get an invitation by code.
    """
    result = await db.execute(
        select(Invitation)
        .where(Invitation.code == code)
        .options(
            joinedload(Invitation.inviter),
            joinedload(Invitation.group)
        )
    )
    return result.scalars().first()

async def get_invitations(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> List[Invitation]:
    """
    Get multiple invitations with pagination.
    """
    result = await db.execute(
        select(Invitation).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_invitations_by_inviter(
    db: AsyncSession, inviter_id: UUID, skip: int = 0, limit: int = 100
) -> List[Invitation]:
    """
    Get invitations by inviter ID.
    """
    result = await db.execute(
        select(Invitation)
        .where(Invitation.inviter_id == inviter_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_invitations_by_group(
    db: AsyncSession, group_id: UUID, skip: int = 0, limit: int = 100
) -> List[Invitation]:
    """
    Get invitations by group ID.
    """
    result = await db.execute(
        select(Invitation)
        .where(Invitation.group_id == group_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_invitation(
    db: AsyncSession, invitation_in: InvitationCreate, inviter_id: UUID
) -> Invitation:
    """
    Create a new invitation.
    """
    # Get inviter for username
    inviter = await db.get(User, inviter_id)
    
    # Generate a unique invitation code
    code = Invitation.generate_code(inviter.username)
    
    # Ensure code is unique
    while await get_invitation_by_code(db, code):
        code = Invitation.generate_code(inviter.username)
    
    # Set expiration date (e.g., 7 days from now)
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    db_invitation = Invitation(
        code=code,
        inviter_id=inviter_id,
        group_id=invitation_in.group_id,
        is_used=False,
        expires_at=expires_at
    )
    db.add(db_invitation)
    await db.commit()
    await db.refresh(db_invitation)
    return db_invitation

async def update_invitation(
    db: AsyncSession, *, db_invitation: Invitation, invitation_in: InvitationUpdate
) -> Invitation:
    """
    Update an invitation.
    """
    invitation_data = invitation_in.model_dump(exclude_unset=True)
    
    # If marking as used, set the used_at timestamp
    if invitation_data.get("is_used") and not db_invitation.is_used:
        invitation_data["used_at"] = datetime.utcnow()
    
    for key, value in invitation_data.items():
        setattr(db_invitation, key, value)
    
    await db.commit()
    await db.refresh(db_invitation)
    return db_invitation

async def delete_invitation(db: AsyncSession, *, invitation_id: UUID) -> Optional[Invitation]:
    """
    Delete an invitation.
    """
    invitation = await get_invitation(db, invitation_id)
    if invitation:
        await db.delete(invitation)
        await db.commit()
    return invitation

async def verify_invitation_code(db: AsyncSession, code: str) -> Optional[Invitation]:
    """
    Verify an invitation code and check if it's valid with improved error handling.
    """
    try:
        logger.info(f"Searching for invitation with code: {code}")
        
        # First, try to find the invitation
        result = await db.execute(
            select(Invitation)
            .where(Invitation.code == code)
            .options(
                joinedload(Invitation.inviter),
                joinedload(Invitation.group)
            )
        )
        invitation = result.scalars().first()
        
        if not invitation:
            logger.warning(f"No invitation found with code: {code}")
            return None
        
        logger.info(f"Found invitation {invitation.id} with code: {code}")
        
        # Check if the invitation is already used
        if invitation.is_used:
            logger.warning(f"Invitation {invitation.id} is already used")
            return None
        
        # Check if the invitation is expired
        if invitation.expires_at and invitation.expires_at < datetime.utcnow():
            logger.warning(f"Invitation {invitation.id} has expired")
            return None
        
        logger.info(f"Invitation {invitation.id} is valid")
        return invitation
        
    except Exception as e:
        logger.error(f"Database error while verifying invitation code {code}: {e}", exc_info=True)
        return None

async def use_invitation(
    db: AsyncSession, invitation_id: UUID, invitee_id: UUID
) -> Optional[Invitation]:
    """
    Mark an invitation as used by a specific invitee.
    """
    invitation = await get_invitation(db, invitation_id)
    
    if not invitation or invitation.is_used:
        return None
    
    invitation.is_used = True
    invitation.invitee_id = invitee_id
    invitation.used_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(invitation)
    return invitation
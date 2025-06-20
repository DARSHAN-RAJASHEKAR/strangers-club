from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
import logging

from app.db.base import get_db
from app.auth.oauth import get_current_active_user
from app.crud import group as crud_group
from app.crud import channel as crud_channel
from app.schemas.group import Group, GroupCreate, GroupUpdate
from app.schemas.channel import Channel, ChannelCreate
from app.schemas.user import User

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("", response_model=List[Group])
async def read_groups(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all groups for the current user.
    """
    logger.info(f"API: Attempting to fetch groups for user_id: {current_user.id}")
    try:
        groups = await crud_group.get_user_groups(db, current_user.id, skip=skip, limit=limit)
        logger.info(f"API: Successfully fetched {len(groups)} groups for user_id: {current_user.id}")
        return groups
    except Exception as e:
        logger.error(f"API: CRITICAL ERROR fetching groups for user_id: {current_user.id} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred while fetching groups.")


@router.post("", response_model=Group)
async def create_group(
    group_in: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new group.
    """
    group = await crud_group.create_group(db, group_in, owner_id=current_user.id)
    return group

@router.get("/owned", response_model=List[Group])
async def read_owned_groups(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all groups owned by the current user.
    """
    groups = await crud_group.get_owned_groups(db, current_user.id, skip=skip, limit=limit)
    return groups

@router.get("/{group_id}", response_model=Group)
async def read_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific group by ID.
    """
    group = await crud_group.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    member_ids = [member.id for member in group.members]
    if current_user.id not in member_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return group

@router.put("/{group_id}", response_model=Group)
async def update_group(
    group_id: UUID,
    group_in: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a group.
    """
    group = await crud_group.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can update the group")
    
    group = await crud_group.update_group(db, db_group=group, group_in=group_in)
    return group

@router.delete("/{group_id}", response_model=Group)
async def delete_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a group.
    """
    group = await crud_group.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    if group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can delete the group")
    
    group = await crud_group.delete_group(db, group_id=group_id)
    return group

@router.post("/{group_id}/channels", response_model=Channel)
async def create_channel(
    group_id: UUID,
    channel_in: ChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Create a new channel in a group.
    """
    group = await crud_group.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    member_ids = [member.id for member in group.members]
    if current_user.id not in member_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    
    channel_data = channel_in.model_dump()
    channel_data["group_id"] = group_id
    
    from app.schemas.channel import ChannelCreate as ChannelCreateSchema
    channel = await crud_channel.create_channel(db, ChannelCreateSchema(**channel_data))
    return channel

@router.get("/{group_id}/channels", response_model=List[Channel])
async def read_channels(
    group_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all channels for a group.
    """
    group = await crud_group.get_group(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    member_ids = [member.id for member in group.members]
    if current_user.id not in member_ids:
        raise HTTPException(status_code=403, detail="Access denied")
    
    channels = await crud_channel.get_channels_by_group(db, group_id, skip=skip, limit=limit)
    return channels

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.db.base import get_db
from app.auth.oauth import get_current_active_user
from app.crud import channel as crud_channel
from app.crud import group as crud_group
from app.schemas.channel import Channel, ChannelCreate, ChannelUpdate
from app.schemas.user import User

router = APIRouter()

@router.get("/{channel_id}", response_model=Channel)
async def read_channel(
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a specific channel by ID.
    """
    channel = await crud_channel.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check if user is a member of the group that owns the channel
    group = await crud_group.get_group(db, channel.group_id)
    if not group or current_user.id not in [member.id for member in group.members]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return channel

@router.put("/{channel_id}", response_model=Channel)
async def update_channel(
    channel_id: UUID,
    channel_in: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update a channel.
    """
    channel = await crud_channel.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check if user is the owner of the group that owns the channel
    group = await crud_group.get_group(db, channel.group_id)
    if not group or group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can update channels")
    
    channel = await crud_channel.update_channel(db, db_channel=channel, channel_in=channel_in)
    return channel

@router.delete("/{channel_id}", response_model=Channel)
async def delete_channel(
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a channel.
    """
    channel = await crud_channel.get_channel(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check if user is the owner of the group that owns the channel
    group = await crud_group.get_group(db, channel.group_id)
    if not group or group.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the group owner can delete channels")
    
    # Prevent deletion of the general channel
    if channel.name == "general":
        raise HTTPException(status_code=400, detail="Cannot delete the general channel")
    
    channel = await crud_channel.delete_channel(db, channel_id=channel_id)
    return channel
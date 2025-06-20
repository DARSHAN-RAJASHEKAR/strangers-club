from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from typing import Optional, List
from uuid import UUID

from app.models.channel import Channel, ChannelType
from app.schemas.channel import ChannelCreate, ChannelUpdate

async def get_channel(db: AsyncSession, channel_id: UUID) -> Optional[Channel]:
    """
    Get a channel by ID with related data.
    """
    result = await db.execute(
        select(Channel)
        .where(Channel.id == channel_id)
        .options(
            joinedload(Channel.group),
        )
    )
    return result.scalars().first()

async def get_channels_by_group(
    db: AsyncSession, group_id: UUID, skip: int = 0, limit: int = 100
) -> List[Channel]:
    """
    Get channels for a specific group.
    """
    result = await db.execute(
        select(Channel)
        .where(Channel.group_id == group_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_channel(
    db: AsyncSession, channel_in: ChannelCreate
) -> Channel:
    """
    Create a new channel.
    """
    db_channel = Channel(
        name=channel_in.name,
        description=channel_in.description,
        type=channel_in.type,
        group_id=channel_in.group_id
    )
    db.add(db_channel)
    await db.commit()
    await db.refresh(db_channel)
    return db_channel

async def update_channel(
    db: AsyncSession, *, db_channel: Channel, channel_in: ChannelUpdate
) -> Channel:
    """
    Update a channel.
    """
    channel_data = channel_in.model_dump(exclude_unset=True)
    for key, value in channel_data.items():
        setattr(db_channel, key, value)
    
    await db.commit()
    await db.refresh(db_channel)
    return db_channel

async def delete_channel(db: AsyncSession, *, channel_id: UUID) -> Optional[Channel]:
    """
    Delete a channel.
    """
    channel = await get_channel(db, channel_id)
    if channel:
        # This will cascade delete all messages
        await db.delete(channel)
        await db.commit()
    return channel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import joinedload
from typing import Optional, List
from uuid import UUID

from app.models.message import Message
from app.schemas.message import MessageCreate, MessageUpdate

async def get_message(db: AsyncSession, message_id: UUID) -> Optional[Message]:
    """
    Get a message by ID with related data.
    """
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id)
        .options(
            joinedload(Message.author),
            joinedload(Message.channel)
        )
    )
    return result.scalars().first()

async def get_messages_by_channel(
    db: AsyncSession, channel_id: UUID, skip: int = 0, limit: int = 50
) -> List[Message]:
    """
    Get messages for a specific channel with pagination.
    """
    result = await db.execute(
        select(Message)
        .where(Message.channel_id == channel_id)
        .options(joinedload(Message.author))
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def get_messages_by_user(
    db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 50
) -> List[Message]:
    """
    Get messages by a specific user with pagination.
    """
    result = await db.execute(
        select(Message)
        .where(Message.author_id == user_id)
        .options(joinedload(Message.channel))
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

async def create_message(
    db: AsyncSession, message_in: MessageCreate, author_id: UUID
) -> Message:
    """
    Create a new message.
    """
    db_message = Message(
        content=message_in.content,
        author_id=author_id,
        channel_id=message_in.channel_id
    )
    db.add(db_message)
    await db.commit()
    await db.refresh(db_message)
    return db_message

async def update_message(
    db: AsyncSession, *, db_message: Message, message_in: MessageUpdate
) -> Message:
    """
    Update a message.
    """
    message_data = message_in.model_dump(exclude_unset=True)
    for key, value in message_data.items():
        setattr(db_message, key, value)
    
    await db.commit()
    await db.refresh(db_message)
    return db_message

async def delete_message(db: AsyncSession, *, message_id: UUID) -> Optional[Message]:
    """
    Delete a message.
    """
    message = await get_message(db, message_id)
    if message:
        await db.delete(message)
        await db.commit()
    return message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional, List
from uuid import UUID

from app.models.user import User
from app.models.group import Group
from app.models.channel import Channel, ChannelType
from app.schemas.group import GroupCreate, GroupUpdate


async def get_group(db: AsyncSession, group_id: UUID) -> Optional[Group]:
    """
    Get a group by ID with all related data eagerly loaded.
    """
    result = await db.execute(
        select(Group)
        .where(Group.id == group_id)
        .options(
            selectinload(Group.owner),
            selectinload(Group.members),
            selectinload(Group.channels)
        )
    )
    return result.scalars().first()


async def get_user_groups(
    db: AsyncSession, user_id: UUID, skip: int = 0, limit: int = 100
) -> List[Group]:
    """
    Get groups for a specific user, eagerly loading members and owners.
    This uses the correct 'any' operator for filtering and 'selectinload' for performance.
    """
    stmt = (
        select(Group)
        .where(Group.members.any(User.id == user_id))
        .options(
            selectinload(Group.owner),
            selectinload(Group.members)
        )
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_owned_groups(
    db: AsyncSession, owner_id: UUID, skip: int = 0, limit: int = 100
) -> List[Group]:
    """
    Get groups owned by a specific user, eagerly loading members.
    """
    result = await db.execute(
        select(Group)
        .where(Group.owner_id == owner_id)
        .options(
            selectinload(Group.owner),
            selectinload(Group.members)
        )
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def create_group(
    db: AsyncSession, group_in: GroupCreate, owner_id: UUID
) -> Group:
    """
    Create a new group with a default general channel.
    """
    # First, get the owner object from the DB
    owner = await db.get(User, owner_id)
    if not owner:
        # This case should ideally not happen if owner_id comes from get_current_user
        raise ValueError("Owner not found")

    db_group = Group(
        name=group_in.name,
        description=group_in.description,
        is_general=group_in.is_general,
        meetup_date=group_in.meetup_date,
        owner_id=owner_id
    )
    
    # Add owner as a member
    db_group.members.append(owner)
    
    db.add(db_group)
    await db.flush()
    
    # Create a default general channel for the group
    default_channel = Channel(
        name="general",
        description="General discussion channel",
        type=ChannelType.GENERAL,
        group_id=db_group.id
    )
    db.add(default_channel)
    
    await db.commit()
    # Eagerly load relationships on the newly created object
    await db.refresh(db_group, attribute_names=['owner', 'members', 'channels'])
    return db_group


async def update_group(
    db: AsyncSession, *, db_group: Group, group_in: GroupUpdate
) -> Group:
    """
    Update a group.
    """
    group_data = group_in.model_dump(exclude_unset=True)
    for key, value in group_data.items():
        setattr(db_group, key, value)
    
    await db.commit()
    await db.refresh(db_group)
    return db_group


async def delete_group(db: AsyncSession, *, group_id: UUID) -> Optional[Group]:
    """
    Delete a group.
    """
    group = await get_group(db, group_id)
    if group:
        await db.delete(group)
        await db.commit()
    return group


async def add_user_to_group(
    db: AsyncSession, group_id: UUID, user_id: UUID
) -> Optional[Group]:
    """
    Add a user to a group.
    """
    group = await get_group(db, group_id)
    user = await db.get(User, user_id)
    
    if not group or not user:
        return None
    
    # Check if user is already a member
    if user.id not in [member.id for member in group.members]:
        group.members.append(user)
        await db.commit()
        await db.refresh(group, attribute_names=['members'])
    
    return group


async def remove_user_from_group(
    db: AsyncSession, group_id: UUID, user_id: UUID
) -> Optional[Group]:
    """
    Remove a user from a group.
    """
    group = await get_group(db, group_id)
    
    user_to_remove = next((member for member in group.members if member.id == user_id), None)

    if not group or not user_to_remove:
        return None
    
    group.members.remove(user_to_remove)
    await db.commit()
    await db.refresh(group, attribute_names=['members'])
    
    return group

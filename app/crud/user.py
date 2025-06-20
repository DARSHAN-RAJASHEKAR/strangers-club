from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from uuid import UUID

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

async def get_user(db: AsyncSession, user_id: UUID) -> Optional[User]:
    """
    Get a user by ID.
    """
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalars().first()

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    Get a user by email, EAGERLY LOADING relationships to prevent lazy-load hangs.
    """
    stmt = (
        select(User)
        .where(User.email == email)
        .options(
            selectinload(User.groups),
            selectinload(User.invitations_received)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    Get a user by username.
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalars().first()

async def get_user_by_google_id(db: AsyncSession, google_id: str) -> Optional[User]:
    """
    Get a user by Google ID.
    """
    result = await db.execute(
        select(User).where(User.google_id == google_id)
    )
    return result.scalars().first()

async def get_users(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> List[User]:
    """
    Get multiple users with pagination.
    """
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """
    Create a new user.
    """
    # Generate a unique username if not provided
    if not user_in.username:
        username = User.generate_username()
        # Ensure username is unique
        while await get_user_by_username(db, username):
            username = User.generate_username()
    else:
        username = user_in.username
    
    db_user = User(
        email=user_in.email,
        username=username,
        google_id=user_in.google_id,
        is_active=True,
        is_superuser=False
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def update_user(
    db: AsyncSession, *, db_user: User, user_in: UserUpdate
) -> User:
    """
    Update a user.
    """
    user_data = user_in.model_dump(exclude_unset=True)
    for key, value in user_data.items():
        setattr(db_user, key, value)
    
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def delete_user(db: AsyncSession, *, user_id: UUID) -> Optional[User]:
    """
    Delete a user.
    """
    user = await get_user(db, user_id)
    if user:
        await db.delete(user)
        await db.commit()
    return user

async def get_or_create_user_by_google_info(
    db: AsyncSession, google_info: Dict[str, Any]
) -> User:
    """
    Gets a user by Google info or creates a new one if it doesn't exist.
    This version eagerly loads the `invitations_received` relationship
    to prevent MissingGreenlet errors in async contexts.
    """
    # 1. Define the query with eager loading
    stmt = (
        select(User)
        .options(selectinload(User.invitations_received))
        .where(User.email == google_info["email"])
    )
    
    result = await db.execute(stmt)
    user = result.scalars().first()
    
    # 2. If user exists, update google_id if necessary
    if user:
        if not user.google_id:
            user.google_id = google_info["id"]
            db.add(user)
            await db.commit()
            await db.refresh(user, attribute_names=['invitations_received'])
        return user

    # 3. If user does not exist, create a new one
    else:
        new_user = User(
            email=google_info["email"],
            google_id=google_info["id"],
            username=User.generate_username()
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user, attribute_names=['invitations_received'])
        return new_user
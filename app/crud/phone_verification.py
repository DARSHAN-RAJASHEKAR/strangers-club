from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta, timezone
import logging

from app.models.phone_verification import PhoneVerification
from app.models.user import User
from app.schemas.phone_verification import PhoneVerificationRequest, UserPhoneUpdate

logger = logging.getLogger(__name__)

async def get_active_verification(
    db: AsyncSession, user_id: UUID, phone_number: str
) -> Optional[PhoneVerification]:
    """
    Get the most recent, non-expired verification for a user and phone number.
    """
    current_time = datetime.now(timezone.utc)
    result = await db.execute(
        select(PhoneVerification)
        .where(
            PhoneVerification.user_id == user_id,
            PhoneVerification.phone_number == phone_number,
            PhoneVerification.expires_at > current_time,
            PhoneVerification.is_verified == False
        )
        .order_by(PhoneVerification.created_at.desc())
    )
    return result.scalars().first()

async def create_verification(
    db: AsyncSession, user_id: UUID, phone_number: str, expires_in_minutes: int = 10
) -> PhoneVerification:
    """
    Create a new phone verification record.
    """
    # Generate verification code
    verification_code = PhoneVerification.generate_verification_code()
    
    # Set expiration time
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
    
    # Create verification record
    verification = PhoneVerification(
        user_id=user_id,
        phone_number=phone_number,
        verification_code=verification_code,
        is_verified=False,
        attempts=0,
        expires_at=expires_at
    )
    
    db.add(verification)
    await db.commit()
    await db.refresh(verification)
    return verification

async def verify_code(
    db: AsyncSession, user_id: UUID, phone_number: str, code: str, max_attempts: int = 3
) -> bool:
    """
    Verify a phone verification code.
    Returns True if verification is successful, False otherwise.
    """
    # Get active verification
    verification = await get_active_verification(db, user_id, phone_number)
    
    if not verification:
        logger.warning(f"No active verification found for user {user_id} and phone {phone_number}")
        return False
    
    # Check if too many attempts
    if verification.attempts >= max_attempts:
        logger.warning(f"Max verification attempts reached for user {user_id} and phone {phone_number}")
        return False
        
    # Update attempts count
    verification.attempts += 1
    
    # Check if code matches
    if verification.verification_code == code:
        # Mark as verified
        verification.is_verified = True
        verification.verified_at = datetime.now(timezone.utc)
        
        # Update user's phone number and verification status
        user = await db.get(User, user_id)
        if user:
            user.phone_number = phone_number
            user.phone_verified = True
            
        await db.commit()
        await db.refresh(verification)
        return True
    else:
        # Code doesn't match
        await db.commit()
        return False

async def invalidate_previous_verifications(
    db: AsyncSession, user_id: UUID, phone_number: str
) -> None:
    """
    Invalidate all previous verification attempts for this user and phone.
    """
    stmt = (
        update(PhoneVerification)
        .where(
            PhoneVerification.user_id == user_id,
            PhoneVerification.phone_number == phone_number,
            PhoneVerification.is_verified == False
        )
        .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    await db.execute(stmt)
    await db.commit()

async def get_user_by_phone(db: AsyncSession, phone_number: str) -> Optional[User]:
    """
    Get a user by phone number.
    """
    result = await db.execute(
        select(User).where(User.phone_number == phone_number, User.phone_verified == True)
    )
    return result.scalars().first()
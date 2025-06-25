import logging
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Dict, Any

from app.db.base import get_db
from app.auth.oauth import get_current_user, create_access_token
from app.crud import phone_verification as crud_phone
from app.schemas.phone_verification import (
    PhoneVerificationRequest, 
    PhoneVerificationCheck,
    PhoneVerificationResponse, 
    PhoneVerificationResult
)
from app.schemas.user import User
from app.services.whatsapp import whatsapp_service
from app.config import settings

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/request-verification", response_model=PhoneVerificationResponse)
async def request_verification(
    request: PhoneVerificationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Request a verification code to be sent to the phone number.
    """
    try:
        # Clean phone number
        phone_number = request.phone_number.strip()
        
        # Check if phone number is already verified by another user
        existing_user = await crud_phone.get_user_by_phone(db, phone_number)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This phone number is already registered with another account"
            )
        
        # Invalidate any previous verification attempts
        await crud_phone.invalidate_previous_verifications(db, current_user.id, phone_number)
        
        # Create new verification
        expires_in_minutes = 10
        verification = await crud_phone.create_verification(
            db, current_user.id, phone_number, expires_in_minutes
        )
        
        # Log the verification code creation
        logger.info(f"Generated verification code {verification.verification_code} for user {current_user.id}")
        
        # Send OTP via WhatsApp - directly call the service (don't use background tasks)
        success = await whatsapp_service.send_otp(
            phone_number=phone_number,
            otp_code=verification.verification_code
        )
        
        if not success:
            # If sending failed, log the error and return appropriate message
            logger.error(f"Failed to send verification code to {phone_number}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification code. Please try again later."
            )
        
        # Calculate seconds until expiration
        expires_in_seconds = int((verification.expires_at - datetime.now(verification.expires_at.tzinfo)).total_seconds())
        
        return PhoneVerificationResponse(
            message=f"Verification code sent to WhatsApp for +91 {phone_number}",
            expires_in=expires_in_seconds
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in request_verification: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification code"
        )

@router.post("/verify-code", response_model=PhoneVerificationResult)
async def verify_code(
    request: PhoneVerificationCheck,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Verify the code sent to the phone number.
    """
    try:
        # Clean inputs
        phone_number = request.phone_number.strip()
        verification_code = request.verification_code.strip()
        
        # Log verification attempt
        logger.info(f"Verification attempt for user {current_user.id} with code {verification_code}")
        
        # Verify the code
        verification_successful = await crud_phone.verify_code(
            db, current_user.id, phone_number, verification_code
        )
        
        if not verification_successful:
            logger.warning(f"Failed verification attempt for user {current_user.id} and phone {phone_number}")
            return PhoneVerificationResult(
                success=False,
                message="Invalid or expired verification code"
            )
        
        logger.info(f"Phone verification successful for user {current_user.id} and phone {phone_number}")
        
        # Create a new access token that includes the verified phone status
        access_token = create_access_token(
            data={"sub": current_user.email},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return PhoneVerificationResult(
            success=True,
            message="Phone number verified successfully",
            token=access_token
        )
        
    except Exception as e:
        logger.error(f"Error in verify_code: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify code"
        )
    
@router.get("/verification-status")
async def get_verification_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get the current user's phone verification status.
    """
    try:
        return {
            "phone_number": current_user.phone_number,
            "is_verified": current_user.phone_verified
        }
    except Exception as e:
        logger.error(f"Error in get_verification_status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get verification status"
        )
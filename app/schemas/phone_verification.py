from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from uuid import UUID
import re

# Phone number validation pattern for Indian numbers (10 digits)
PHONE_PATTERN = re.compile(r"^[6-9]\d{9}$")

class PhoneBase(BaseModel):
    phone_number: str
    
    @validator('phone_number')
    def validate_phone(cls, v):
        """Validate that the phone number is a valid Indian mobile number."""
        if not PHONE_PATTERN.match(v):
            raise ValueError('Phone number must be a valid 10-digit Indian mobile number starting with 6-9')
        return v

# Request to send verification code
class PhoneVerificationRequest(PhoneBase):
    pass

# Request to verify code
class PhoneVerificationCheck(PhoneBase):
    verification_code: str = Field(..., min_length=6, max_length=6)

# Response from verification request
class PhoneVerificationResponse(BaseModel):
    message: str
    expires_in: int  # Seconds until expiration
    
# Response from verification check
class PhoneVerificationResult(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None  # New token if verification was successful

# Phone number update for user schema
class UserPhoneUpdate(BaseModel):
    phone_number: Optional[str] = None
    phone_verified: Optional[bool] = None
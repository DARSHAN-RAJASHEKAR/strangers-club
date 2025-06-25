import uuid
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import GUID  # Import the custom GUID type

class PhoneVerification(Base):
    __tablename__ = "phone_verifications"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    phone_number = Column(String, index=True, nullable=False)  # Format: 10-digit number (Indian)
    verification_code = Column(String(6), nullable=False)  # 6-digit code
    is_verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)  # Track verification attempts
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="phone_verifications")
    
    @staticmethod
    def generate_verification_code() -> str:
        """Generate a random 6-digit verification code."""
        return str(random.randint(100000, 999999))
    
    @property
    def is_expired(self) -> bool:
        """Check if the verification code has expired."""
        return datetime.now(timezone.utc) > self.expires_at
    
    @property
    def formatted_phone(self) -> str:
        """Return the phone number formatted with country code (91)."""
        return f"91{self.phone_number}"
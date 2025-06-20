import uuid
import random
import string
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import GUID  # Import the custom GUID type

class Invitation(Base):
    __tablename__ = "invitations"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)  # Use GUID instead of UUID
    code = Column(String, unique=True, index=True, nullable=False)
    inviter_id = Column(GUID, ForeignKey("users.id"), nullable=False)  # Use GUID instead of UUID
    invitee_id = Column(GUID, ForeignKey("users.id"), nullable=True)  # Use GUID instead of UUID
    group_id = Column(GUID, ForeignKey("groups.id"), nullable=False)  # Use GUID instead of UUID
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    inviter = relationship("User", foreign_keys=[inviter_id], back_populates="invitations_sent")
    invitee = relationship("User", foreign_keys=[invitee_id], back_populates="invitations_received")
    group = relationship("Group", back_populates="invitations")
    
    @staticmethod
    def generate_code(username: str) -> str:
        """Generate an invitation code based on username plus one letter and two digits."""
        letter = random.choice(string.ascii_uppercase)
        digits = ''.join(random.choices(string.digits, k=2))
        return f"{username}-{letter}{digits}"
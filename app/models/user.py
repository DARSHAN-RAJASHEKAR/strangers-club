import uuid
import random
import string
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import List, Optional

from app.db.base import Base
from app.db.types import GUID  # Import the custom GUID type

# Association table for user-group many-to-many relationship
user_group = Table(
    "user_group",
    Base.metadata,
    Column("user_id", GUID, ForeignKey("users.id"), primary_key=True),  # Use GUID instead of UUID
    Column("group_id", GUID, ForeignKey("groups.id"), primary_key=True)  # Use GUID instead of UUID
)

class User(Base):
    __tablename__ = "users"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)  # Use GUID instead of UUID
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    google_id = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    groups = relationship("Group", secondary=user_group, back_populates="members")
    owned_groups = relationship("Group", back_populates="owner")
    invitations_sent = relationship("Invitation", foreign_keys="Invitation.inviter_id", back_populates="inviter")
    invitations_received = relationship("Invitation", foreign_keys="Invitation.invitee_id", back_populates="invitee")
    messages = relationship("Message", back_populates="author")

    @staticmethod
    def generate_username() -> str:
        """Generate a random username with 2 letters and 3 digits."""
        letters = ''.join(random.choices(string.ascii_uppercase, k=2))
        digits = ''.join(random.choices(string.digits, k=3))
        return f"{letters}{digits}"
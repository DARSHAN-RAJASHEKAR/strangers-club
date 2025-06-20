import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.models.user import user_group
from app.db.types import GUID  # Import the custom GUID type

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)  # Use GUID instead of UUID
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_general = Column(Boolean, default=False)  # Is this a general group for all users?
    meetup_date = Column(DateTime(timezone=True), nullable=True)  # For meetup journal groups
    owner_id = Column(GUID, ForeignKey("users.id"), nullable=False)  # Use GUID instead of UUID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    owner = relationship("User", back_populates="owned_groups")
    members = relationship("User", secondary=user_group, back_populates="groups")
    channels = relationship("Channel", back_populates="group")
    invitations = relationship("Invitation", back_populates="group")
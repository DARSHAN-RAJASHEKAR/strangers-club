import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.db.base import Base
from app.db.types import GUID  # Import the custom GUID type

class ChannelType(str, enum.Enum):
    GENERAL = "general"
    HOBBY = "hobby"
    INTEREST = "interest"
    MEETUP = "meetup"
    OTHER = "other"

class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)  # Use GUID instead of UUID
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(Enum(ChannelType), default=ChannelType.GENERAL)
    group_id = Column(GUID, ForeignKey("groups.id"), nullable=False)  # Use GUID instead of UUID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    group = relationship("Group", back_populates="channels")
    messages = relationship("Message", back_populates="channel")
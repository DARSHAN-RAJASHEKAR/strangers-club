import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.types import GUID  # Import the custom GUID type

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(GUID, primary_key=True, default=uuid.uuid4)  # Use GUID instead of UUID
    content = Column(Text, nullable=False)
    author_id = Column(GUID, ForeignKey("users.id"), nullable=False)  # Use GUID instead of UUID
    channel_id = Column(GUID, ForeignKey("channels.id"), nullable=False)  # Use GUID instead of UUID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    author = relationship("User", back_populates="messages")
    channel = relationship("Channel", back_populates="messages")
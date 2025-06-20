from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

from app.schemas.user import User

# Shared properties
class MessageBase(BaseModel):
    content: str

# Properties to receive via API on creation
class MessageCreate(MessageBase):
    channel_id: UUID

# Properties to receive via API on update
class MessageUpdate(MessageBase):
    content: Optional[str] = None

# Properties shared by models stored in DB
class MessageInDBBase(MessageBase):
    id: UUID
    author_id: UUID
    channel_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Properties to return via API
class Message(MessageInDBBase):
    author: Optional[User] = None

# Additional properties stored in DB
class MessageInDB(MessageInDBBase):
    pass
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from enum import Enum

class ChannelTypeEnum(str, Enum):
    GENERAL = "general"
    HOBBY = "hobby"
    INTEREST = "interest"
    MEETUP = "meetup"
    OTHER = "other"

# Shared properties
class ChannelBase(BaseModel):
    name: str
    description: Optional[str] = None
    type: ChannelTypeEnum = ChannelTypeEnum.GENERAL

# Properties to receive via API on creation
class ChannelCreate(ChannelBase):
    group_id: UUID

# Properties to receive via API on update
class ChannelUpdate(ChannelBase):
    name: Optional[str] = None
    type: Optional[ChannelTypeEnum] = None

# Properties shared by models stored in DB
class ChannelInDBBase(ChannelBase):
    id: UUID
    group_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Properties to return via API
class Channel(ChannelInDBBase):
    pass

# Additional properties stored in DB
class ChannelInDB(ChannelInDBBase):
    pass
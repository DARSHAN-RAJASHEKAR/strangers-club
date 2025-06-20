from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.schemas.user import User

# Shared properties
class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_general: bool = False
    meetup_date: Optional[datetime] = None

# Properties to receive via API on creation
class GroupCreate(GroupBase):
    pass

# Properties to receive via API on update
class GroupUpdate(GroupBase):
    name: Optional[str] = None

# Properties shared by models stored in DB
class GroupInDBBase(GroupBase):
    id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Properties to return via API
class Group(GroupInDBBase):
    owner: Optional[User] = None
    member_count: Optional[int] = None

# Additional properties stored in DB
class GroupInDB(GroupInDBBase):
    pass
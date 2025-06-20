from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

# Shared properties
class InvitationBase(BaseModel):
    group_id: UUID

# Properties to receive via API on creation
class InvitationCreate(InvitationBase):
    pass

# Properties to receive via API on update
class InvitationUpdate(InvitationBase):
    is_used: Optional[bool] = None
    invitee_id: Optional[UUID] = None

# Properties shared by models stored in DB
class InvitationInDBBase(InvitationBase):
    id: UUID
    code: str
    inviter_id: UUID
    invitee_id: Optional[UUID] = None
    is_used: bool
    created_at: datetime
    used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Properties to return via API
class Invitation(InvitationInDBBase):
    pass

# Additional properties stored in DB
class InvitationInDB(InvitationInDBBase):
    pass

# Invitation verification
class InvitationVerify(BaseModel):
    code: str
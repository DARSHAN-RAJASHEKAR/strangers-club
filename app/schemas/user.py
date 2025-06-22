from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    is_active: Optional[bool] = True

# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    google_id: Optional[str] = None

# Properties to receive via API on update
class UserUpdate(UserBase):
    pass

# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: UUID
    email: EmailStr
    username: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Properties to return via API
class User(UserInDBBase):
    is_superuser: bool = False

# Additional properties stored in DB
class UserInDB(UserInDBBase):
    is_superuser: bool
    google_id: Optional[str] = None

# Token schema
class Token(BaseModel):
    access_token: str
    token_type: str

# Token data schema
class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None

# Google OAuth user info
class GoogleUserInfo(BaseModel):
    id: str
    email: EmailStr
    verified_email: bool
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None
    locale: Optional[str] = None
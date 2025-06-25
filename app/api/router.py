from fastapi import APIRouter

from app.api.endpoints import auth, groups, invitations, channels, messages, phone_verification

api_router = APIRouter()

# Auth routes
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Group routes
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])

# Invitation routes
api_router.include_router(invitations.router, prefix="/invitations", tags=["invitations"])

# Channel routes
api_router.include_router(channels.router, prefix="/channels", tags=["channels"])

# Message routes
api_router.include_router(messages.router, prefix="/messages", tags=["messages"])

# Add this line inside the api_router setup
api_router.include_router(phone_verification.router, prefix="/phone", tags=["phone"])
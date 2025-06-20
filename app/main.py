import datetime
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from pathlib import Path
import uvicorn
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.router import api_router
from app.config import settings
from app.db.base import Base, engine, get_db
from app.models.group import Group
from app.models.channel import Channel, ChannelType
from app.models.user import User

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Add SessionMiddleware for OAuth
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY,
                   session_cookie="session",
                   max_age=60 * 60 * 24 * 7,
                   same_site="lax",
                   https_only=False)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Database initialization
@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        # Create tables if they don't exist
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        # --- ROBUST ADMIN CREATION ---
        # Find user by email first.
        result = await session.execute(
            select(User).where(User.email == "timeleftclub@gmail.com")
        )
        admin = result.scalars().first()

        if admin:
            # If user exists, ensure they are a superuser.
            if not admin.is_superuser:
                admin.is_superuser = True
                session.add(admin)
                await session.commit()
                await session.refresh(admin)
        else:
            # If user does not exist, create them as a superuser.
            admin = User(
                email="timeleftclub@gmail.com",
                username="ADMIN",
                is_active=True,
                is_superuser=True
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
        
        # --- GENERAL GROUP CREATION ---
        # Now that we have a guaranteed admin, check for the general group.
        result = await session.execute(
            select(Group).where(Group.is_general == True)
        )
        general_group = result.scalars().first()
        
        if not general_group:
            # Create general group, owned by the admin user
            general_group = Group(
                name="General",
                description="General group for all users",
                is_general=True,
                owner_id=admin.id
            )
            general_group.members.append(admin)
            session.add(general_group)
            await session.flush() # Use flush to get the group ID before commit
            
            # Create general channel
            general_channel = Channel(
                name="general",
                description="General discussion channel",
                type=ChannelType.GENERAL,
                group_id=general_group.id
            )
            session.add(general_channel)
            
            await session.commit()

# Root route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Render the landing page.
    """
    return templates.TemplateResponse("index.html", {"request": request})

# Login page
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    error = request.query_params.get("error")
    return templates.TemplateResponse("login.html", {
        "request": request,
        "debug": settings.DEBUG,
        "error": error
    })

# Invitation page
@app.get("/invite", response_class=HTMLResponse)
async def invite_page(request: Request):
    token = request.query_params.get("token", "")
    return templates.TemplateResponse("invite.html", {"request": request, "token": token})

# App page (requires authentication)
@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    token = request.query_params.get("token", "")
    return templates.TemplateResponse("dashboard.html", {"request": request, "token": token})

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok"}

def create_jinja2_environment():
    env = templates.env
    env.globals.update({
        "now": lambda format_string: datetime.datetime.now().strftime(format_string)
    })
    return env
templates.env = create_jinja2_environment()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

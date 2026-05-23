import datetime
import os
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
import subprocess
import sys

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

# Add SessionMiddleware with production-ready settings
app.add_middleware(
    SessionMiddleware, 
    secret_key=settings.session_secret,
    session_cookie="sessionid",
    max_age=60 * 60 * 24 * 7,  # 7 days
    same_site="lax",
    https_only=settings.use_https
)

# Set up CORS with production settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Set up templates
templates = Jinja2Templates(directory="templates")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

def run_alembic_upgrade():
    """Run alembic upgrade head to ensure database is up to date"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode != 0:
            print(f"Alembic upgrade failed: {result.stderr}")
            raise Exception(f"Database migration failed: {result.stderr}")
        else:
            print("Database migrations applied successfully")
            print(result.stdout)
    except Exception as e:
        print(f"Error running migrations: {e}")
        raise

# Database initialization
@app.on_event("startup")
async def init_db():
    # Run database migrations first
    if settings.is_production:
        print("Running database migrations...")
        run_alembic_upgrade()
    
    async with AsyncSession(engine) as session:
        # --- ROBUST ADMIN CREATION ---
        # Find user by email first.
        result = await session.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
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
                email=settings.ADMIN_EMAIL,
                username="ADMIN",
                is_active=True,
                is_superuser=True
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)

        # --- DEMO LOUNGE (shared group for all demo users) ---
        result = await session.execute(
            select(Group).where(Group.name == "Demo Lounge")
        )
        lounge = result.scalars().first()
        if not lounge:
            result = await session.execute(
                select(User).where(User.email == settings.ADMIN_EMAIL)
            )
            admin_user = result.scalars().first()
            if admin_user:
                lounge = Group(
                    name="Demo Lounge",
                    description="Shared space for demo users to chat",
                    is_general=True,
                    owner_id=admin_user.id,
                )
                session.add(lounge)
                await session.commit()
                await session.refresh(lounge)
                session.add(Channel(
                    name="general",
                    description="Demo chat",
                    type=ChannelType.GENERAL,
                    group_id=lounge.id,
                ))
                await session.commit()
                print("Demo Lounge created")

    asyncio.create_task(_demo_cleanup_loop())


async def _delete_demo_groups(session: AsyncSession, demo_user_id, cutoff=None):
    """Delete demo groups and all related rows using raw SQL to avoid ORM cascade issues."""
    from sqlalchemy import text

    q = "SELECT id FROM groups WHERE owner_id = :uid"
    params = {"uid": str(demo_user_id)}
    if cutoff:
        q += " AND created_at < :cutoff"
        params["cutoff"] = cutoff.isoformat()

    result = await session.execute(text(q), params)
    group_ids = [str(row[0]) for row in result.fetchall()]
    if not group_ids:
        return

    # Parameterized IN clause — SQLite requires individual named params, not tuple binding
    params = {f"gid_{i}": gid for i, gid in enumerate(group_ids)}
    id_list = ", ".join(f":gid_{i}" for i in range(len(group_ids)))

    await session.execute(text(f"DELETE FROM messages WHERE channel_id IN (SELECT id FROM channels WHERE group_id IN ({id_list}))"), params)
    await session.execute(text(f"DELETE FROM channels WHERE group_id IN ({id_list})"), params)
    await session.execute(text(f"DELETE FROM invitations WHERE group_id IN ({id_list})"), params)
    await session.execute(text(f"DELETE FROM user_group WHERE group_id IN ({id_list})"), params)
    await session.execute(text(f"DELETE FROM groups WHERE id IN ({id_list})"), params)
    await session.commit()


async def _demo_cleanup_loop():
    """Every 5 min: delete demo groups >30 min old. Every 48h: delete all demo users."""
    from datetime import timezone
    from sqlalchemy import text
    last_user_cleanup = datetime.datetime.now(timezone.utc)

    while True:
        await asyncio.sleep(5 * 60)
        try:
            async with AsyncSession(engine) as session:
                now = datetime.datetime.now(timezone.utc)

                # Delete demo groups older than 30 min (skip Demo Lounge)
                cutoff_groups = now - datetime.timedelta(minutes=30)
                result = await session.execute(
                    select(User).where(User.email.like("demo%@demo.strangers.club"))
                )
                demo_users = result.scalars().all()
                for du in demo_users:
                    await _delete_demo_groups(session, du.id, cutoff=cutoff_groups)

                # Every 48h: delete all demo users and their remaining data
                if (now - last_user_cleanup).total_seconds() >= 48 * 3600:
                    result = await session.execute(
                        select(User).where(User.email.like("demo%@demo.strangers.club"))
                    )
                    demo_users = result.scalars().all()
                    for du in demo_users:
                        await _delete_demo_groups(session, du.id)
                        # Delete invitations where this demo user is the inviter (FK constraint)
                        await session.execute(
                            text("DELETE FROM invitations WHERE inviter_id = :uid"),
                            {"uid": str(du.id)}
                        )
                        await session.execute(
                            text("DELETE FROM user_group WHERE user_id = :uid"),
                            {"uid": str(du.id)}
                        )
                        await session.delete(du)
                    await session.commit()
                    last_user_cleanup = now
                    print("Demo users purged (48h cycle)")

        except Exception as e:
            print(f"Demo cleanup error: {e}")


# Root route
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """
    Render the landing page.
    """
    error = request.query_params.get("error")
    # Clear session token on landing page to ensure fresh start if they are here
    # (except if they are logged in, the JS on index.html will redirect them, but let's clear it if there's an error)
    if error:
        request.session.pop("token", None)
    return templates.TemplateResponse("index.html", {"request": request, "error": error})

# Logout route
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

# Invitation page (for platform registration)
@app.get("/invite", response_class=HTMLResponse)
async def invite_page(request: Request):
    token = request.session.get("token", "") or request.query_params.get("token", "")
    if not token:
        return RedirectResponse(url="/")
    if request.query_params.get("token"):
        request.session["token"] = request.query_params.get("token")
        return RedirectResponse(url="/invite")
    return templates.TemplateResponse("invite.html", {"request": request, "token": token})

# Join group page (for joining groups with invitation codes)
@app.get("/join-group", response_class=HTMLResponse)
async def join_group_page(request: Request):
    return templates.TemplateResponse("join-group.html", {"request": request})

# App page (requires authentication)
@app.get("/app", response_class=HTMLResponse)
async def app_page(request: Request):
    token = request.session.get("token", "") or request.query_params.get("token", "")
    
    if not token:
        return RedirectResponse(url="/")
    
    # Migrate query-param token into session and redirect to clean URL
    if request.query_params.get("token"):
        request.session["token"] = request.query_params.get("token")
        return RedirectResponse(url="/app")
    
    # Server-side guard: redirect unverified users before rendering dashboard
    try:
        from jose import jwt, JWTError
        from app.crud.user import get_user_by_email
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_email = payload.get("sub")
        if user_email:
            async with AsyncSession(engine) as session:
                user = await get_user_by_email(session, email=user_email)
                if user and not user.phone_verified and not user.is_superuser:
                    return RedirectResponse(url="/verify-phone")
    except (JWTError, Exception):
        pass  # Let the client-side handle invalid tokens
    
    return templates.TemplateResponse("dashboard.html", {"request": request, "token": token})

# Phone verification page
@app.get("/verify-phone", response_class=HTMLResponse)
async def verify_phone_page(request: Request):
    token = request.session.get("token", "") or request.query_params.get("token", "")
    
    if not token:
        return RedirectResponse(url="/")
    
    # Migrate query-param token into session and redirect to clean URL
    if request.query_params.get("token"):
        request.session["token"] = request.query_params.get("token")
        return RedirectResponse(url="/verify-phone")
    
    return templates.TemplateResponse("verify-phone.html", {"request": request, "token": token})

# House rules page
@app.get("/house-rules", response_class=HTMLResponse)
async def house_rules_page(request: Request):
    return templates.TemplateResponse("house-rules.html", {"request": request})

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": os.getenv("ENVIRONMENT", "development")}

def create_jinja2_environment():
    env = templates.env
    env.globals.update({
        "now": lambda format_string: datetime.datetime.now().strftime(format_string)
    })
    return env

templates.env = create_jinja2_environment()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Use single worker for development
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
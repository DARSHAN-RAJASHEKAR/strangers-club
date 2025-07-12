Strangers Meet
Strangers Meet is an invite-only social platform designed to help people maintain connections with others they meet in real life. The platform combines group messaging, meetup planning, and secure phone verification to create a trusted community for meaningful connections.
🌟 Features
Core Functionality

Invite-Only Registration: New users require invitation codes from existing members
Google OAuth Authentication: Secure login using Gmail accounts
Phone Verification: WhatsApp-based phone number verification for security
Real-time Group Chat: WebSocket-powered messaging with offline support
Group Management: Create and manage Timeleft Meet-Up Groups and General Groups

Group Types

Timeleft Meet-Up Groups: Private groups for specific meetups with optional dates
General Groups: Platform-wide groups for broader community discussions

Communication Features

Real-time messaging with WebSocket connections
Offline message queuing for reliable delivery
Typing indicators to show when users are typing
Message persistence with local storage backup
Connection status indicators for real-time chat availability

Security & Verification

JWT-based authentication with configurable expiration
Phone verification via WhatsApp using Gupshup.io API
Invitation code system for controlled user registration
Admin controls for platform management

🏗️ Architecture
Backend (FastAPI)

FastAPI framework with async/await support
SQLAlchemy with PostgreSQL for production, SQLite for development
Alembic for database migrations
Pydantic for data validation and serialization
JWT for secure authentication

Frontend

Jinja2 templates with Alpine.js for interactivity
Tailwind CSS for responsive styling
WebSocket connections for real-time features
Offline-first approach with local storage

Database Schema

Users: Authentication and profile information
Groups: Timeleft meetups and general discussion groups
Channels: Communication channels within groups
Messages: Chat messages with real-time sync
Invitations: Secure invitation code system
Phone Verifications: WhatsApp-based verification records

🚀 Quick Start
Prerequisites

Python 3.12+
PostgreSQL (for production) or SQLite (for development)
Google OAuth credentials
Gupshup.io WhatsApp API credentials (optional, for phone verification)

Installation

Clone the repository
bashgit clone <repository-url>
cd strangers-meet

Install dependencies
bashpip install -r requirements.txt

Environment Setup
Create a .env file in the root directory:
env# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost/strangers_meet
# For development, you can use SQLite:
DATABASE_URL=sqlite+aiosqlite:///./strangers_meet.db

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# WhatsApp API (Gupshup.io)
GUPSHUP_API_KEY=your-gupshup-api-key
GUPSHUP_SOURCE_NUMBER=your-whatsapp-business-number
GUPSHUP_APP_NAME=your-app-name
GUPSHUP_TEMPLATE_ID=your-template-id

# Optional
DEBUG=true
FRONTEND_URL=http://localhost:8000

Database Setup
bash# Run database migrations
alembic upgrade head

Run the Application
bash# Development
python app/main.py

# Or with uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

Access the Application
Open your browser and navigate to http://localhost:8000

🔧 Configuration
Google OAuth Setup

Go to Google Cloud Console
Create a new project or select existing one
Enable Google+ API
Create OAuth 2.0 credentials
Add authorized redirect URI: http://localhost:8000/api/v1/auth/google/callback

WhatsApp API Setup (Optional)

Sign up at Gupshup.io
Create a WhatsApp Business API app
Set up a message template for OTP verification
Get your API key and configure the template ID

Database Configuration
The application supports both PostgreSQL (production) and SQLite (development):
PostgreSQL (Recommended for production):
envDATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/strangers_meet
SQLite (Development):
envDATABASE_URL=sqlite+aiosqlite:///./strangers_meet.db
📱 Usage
For New Users

Get an Invitation: Ask an existing user for an invitation code
Login: Use Google OAuth to sign in
Enter Invitation Code: Complete registration with your invitation code
Phone Verification: Verify your WhatsApp number
Start Chatting: Join groups and start conversations

For Existing Users

Generate Invitation Codes: Create codes for new users or specific groups
Create Groups: Set up new Timeleft Meet-Up Groups
Join Groups: Use invitation codes to join existing groups
Chat in Real-time: Send messages with instant delivery

Admin Features

Platform Invitations: Generate registration codes for new users
General Groups: Create platform-wide discussion groups
User Management: Manage user permissions and access

🏢 Deployment
Render.com (Recommended)
The application is configured for easy deployment on Render.com:

Connect Repository: Link your GitHub repository to Render
Environment Variables: Set all required environment variables
Database: Use Render's managed PostgreSQL service
Deploy: Automatic deployment from main branch

Manual Deployment
bash# Set production environment
export RENDER=true

# Install dependencies
pip install -r requirements.txt

# Run migrations
python -m alembic upgrade head

# Start with gunicorn
gunicorn app.main:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
🔒 Security Features

Invite-only registration prevents spam and unauthorized access
Phone verification adds an extra layer of security
JWT tokens with configurable expiration times
CORS protection with configurable origins
Input validation using Pydantic schemas
SQL injection prevention through SQLAlchemy ORM

🛠️ Development
Project Structure
strangers-meet/
├── app/
│   ├── api/
│   │   └── endpoints/          # API route handlers
│   ├── auth/                   # Authentication logic
│   ├── crud/                   # Database operations
│   ├── db/                     # Database configuration
│   ├── models/                 # SQLAlchemy models
│   ├── schemas/                # Pydantic schemas
│   ├── services/               # External service integrations
│   ├── config.py               # Application configuration
│   └── main.py                 # Application entry point
├── templates/                  # Jinja2 HTML templates
├── static/                     # CSS, JS, and assets
├── alembic/                    # Database migrations
├── requirements.txt            # Python dependencies
├── Procfile                    # Render.com deployment config
└── README.md                   # This file
Database Migrations
bash# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
Running Tests
bash# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest

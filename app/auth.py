"""
Authentication middleware and utilities for News Digest Agent
Provides password protection with session-based authentication
"""

from fastapi import Request, HTTPException, Depends, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import secrets
from typing import Optional, Dict, Any
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Session storage (in production, use Redis or database)
active_sessions: Dict[str, Dict[str, Any]] = {}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)

def create_session_token() -> str:
    """Create a secure session token"""
    return secrets.token_urlsafe(32)

def create_session(username: str) -> str:
    """Create a new session and return token"""
    token = create_session_token()
    active_sessions[token] = {
        "username": username,
        "created_at": datetime.utcnow(),
        "last_activity": datetime.utcnow()
    }
    return token

def get_session(token: str) -> Optional[Dict[str, Any]]:
    """Get session data by token"""
    session = active_sessions.get(token)
    if session:
        # Update last activity
        session["last_activity"] = datetime.utcnow()
        
        # Check if session is expired (24 hours)
        if datetime.utcnow() - session["created_at"] > timedelta(hours=24):
            del active_sessions[token]
            return None
        
        return session
    return None

def delete_session(token: str):
    """Delete a session"""
    if token in active_sessions:
        del active_sessions[token]

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate user credentials"""
    if not settings.enable_auth:
        return True
    
    # Check against configured credentials
    if username == settings.auth_username:
        # If no hashed password is set, hash the plain password from env
        if settings.auth_password and not settings.auth_password.startswith("$2b$"):
            # Plain text password - hash it (for development)
            return password == settings.auth_password
        else:
            # Hashed password
            return verify_password(password, settings.auth_password)
    
    return False

def get_current_user(request: Request) -> Optional[str]:
    """Get current authenticated user from session"""
    if not settings.enable_auth:
        return "anonymous"
    
    # Check session cookie
    session_token = request.cookies.get("session_token")
    if session_token:
        session = get_session(session_token)
        if session:
            return session["username"]
    
    return None

def require_auth(request: Request) -> str:
    """Dependency that requires authentication"""
    user = get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

# Templates for login page
templates = Jinja2Templates(directory="app/templates")

async def render_login_page(request: Request, error: str = None):
    """Render login page"""
    return templates.TemplateResponse(
        "login.html", 
        {"request": request, "error": error}
    )

def login_required_redirect(request: Request):
    """Redirect to login if not authenticated"""
    if not settings.enable_auth:
        return None
        
    user = get_current_user(request)
    if user is None:
        # Store the original URL for redirect after login
        return RedirectResponse(url="/login", status_code=302)
    
    return None

class AuthMiddleware:
    """Authentication middleware"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        path = request.url.path
        
        # Skip auth for login/logout pages and static files
        skip_auth_paths = ["/login", "/logout", "/static", "/health"]
        
        if not settings.enable_auth or any(path.startswith(p) for p in skip_auth_paths):
            await self.app(scope, receive, send)
            return
        
        # Check authentication
        user = get_current_user(request)
        if user is None:
            # Redirect to login
            response = RedirectResponse(url="/login")
            await response(scope, receive, send)
            return
        
        await self.app(scope, receive, send)

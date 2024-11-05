from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests
import os
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import logging

from app.database import get_db
from app.models.auth import User, UserRole

# Set up logging
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # Set to 24 hours

# Define recruiter emails - moved to top level
RECRUITER_EMAILS = {
    "abhilashnl2006@gmail.com",
    "abhinl2006@gmail.com",
      # Add more recruiter emails as needed
}

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def determine_user_role(email: str) -> UserRole:
    """Determine user role based on email"""
    is_recruiter = email in RECRUITER_EMAILS
    role = UserRole.RECRUITER if is_recruiter else UserRole.CANDIDATE
    logger.info(f"Determining role for {email}: {'RECRUITER' if is_recruiter else 'CANDIDATE'}")
    logger.info(f"Current RECRUITER_EMAILS: {RECRUITER_EMAILS}")
    return role

def verify_google_token(token: str):
    """Verify Google OAuth2 token and return user info"""
    try:
        idinfo = id_token.verify_oauth2_token(
            token, requests.Request(), GOOGLE_CLIENT_ID)

        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Invalid issuer')

        return {
            'email': idinfo['email'],
            'name': idinfo['name'],
            'picture': idinfo.get('picture'),
            'google_id': idinfo['sub']
        }
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token"
        )

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create JWT access token with enhanced logging and longer default expiration
    
    Args:
        data (dict): Data to encode in the token
        expires_delta (Optional[timedelta]): Optional custom expiration time
        
    Returns:
        str: Encoded JWT token
    """
    try:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            # Set default expiration to 24 hours instead of 30 minutes
            expire = datetime.utcnow() + timedelta(hours=24)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        logger.info(f"Created access token for user: {data.get('email', 'unknown')}")
        logger.debug(f"Token expires at: {expire}")
        
        return encoded_jwt
        
    except Exception as e:
        logger.error(f"Error creating access token: {str(e)}")
        raise

def verify_token(token: str):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_user(
    auth: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from token"""
    try:
        payload = verify_token(auth.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )
    except JWTError as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user
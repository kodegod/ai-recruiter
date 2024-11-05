from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Body
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
from typing import Optional
from google.oauth2 import id_token
from google.auth.transport import requests
import os
import logging

from app.database import get_db
from app.models.auth import User, UserRole, UserSession
from app.utils.auth import (verify_google_token, create_access_token,
                          verify_token, get_current_user,
                          determine_user_role, RECRUITER_EMAILS)

# Set up logging
logger = logging.getLogger(__name__)

# Create the router instance
router = APIRouter(prefix="/auth", tags=["authentication"])

# OAuth2 scheme for JWT
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/google-login")
async def google_login(token: dict = Body(...), db: Session = Depends(get_db)):
    """Handle Google login and return JWT token"""
    try:
        # Log incoming request
        logger.info("Received login request")

        # Extract token
        if isinstance(token, dict) and 'token' in token:
            credential = token['token']
        else:
            credential = token

        # Verify Google token
        try:
            user_data = verify_google_token(credential)
            logger.info(f"Verified user data for email: {user_data.get('email')}")
        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google token: {str(e)}"
            )

        # Get current role for this email
        current_role = determine_user_role(user_data['email'])
        logger.info(f"Determined role for {user_data['email']}: {current_role}")

        # Check if user exists
        user = db.query(User).filter(User.email == user_data['email']).first()

        if not user:
            logger.info(f"Creating new user with role {current_role} for email: {user_data['email']}")
            user = User(
                email=user_data['email'],
                name=user_data['name'],
                picture=user_data.get('picture'),
                google_id=user_data['google_id'],
                role=current_role
            )
            db.add(user)
        else:
            logger.info(f"Found existing user with ID: {user.id}")
            # Update user role if it has changed
            if user.role != current_role:
                logger.info(f"Updating user role from {user.role} to {current_role}")
                user.role = current_role
            # Update other fields that might have changed
            user.name = user_data['name']
            user.picture = user_data.get('picture')

        # Update last login
        user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(user)

        # Create access token
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "role": user.role,
                "email": user.email
            }
        )

        # Create session
        session = UserSession(
            user_id=user.id,
            session_token=access_token,
            expires_at=datetime.utcnow() + timedelta(days=1)
        )
        db.add(session)
        db.commit()
        logger.info(f"Created new session for user: {user.id}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "picture": user.picture
            }
        }

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/me")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    try:
        return {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role,
            "picture": current_user.picture
        }
    except Exception as e:
        logger.error(f"Error getting user info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user information"
        )

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout user and invalidate session"""
    try:
        # Remove session from database
        sessions_deleted = db.query(UserSession).filter(
            UserSession.user_id == current_user.id,
            UserSession.expires_at > datetime.utcnow()
        ).delete()
        db.commit()
        
        logger.info(f"Logged out user {current_user.id}. Deleted {sessions_deleted} sessions.")
        return {"message": "Successfully logged out"}
        
    except SQLAlchemyError as e:
        logger.error(f"Database error during logout: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during logout"
        )
    except Exception as e:
        logger.error(f"Unexpected error during logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during logout"
        )

@router.post("/refresh-token")
async def refresh_token(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Refresh the access token"""
    try:
        # Create new access token
        access_token = create_access_token(
            data={
                "sub": str(current_user.id),
                "role": current_user.role,
                "email": current_user.email
            }
        )
        
        # Update or create session
        session = UserSession(
            user_id=current_user.id,
            session_token=access_token,
            expires_at=datetime.utcnow() + timedelta(days=1)
        )
        db.add(session)
        db.commit()
        
        logger.info(f"Token refreshed for user: {current_user.id}")
        return {
            "access_token": access_token,
            "token_type": "bearer"
        }
        
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error refreshing token"
        )
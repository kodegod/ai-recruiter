from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.auth import verify_token
from app.models.auth import UserRole, User
from typing import Optional, List
from app.database import get_db
import logging

# Set up logging
logger = logging.getLogger(__name__)

security = HTTPBearer()

class AuthMiddleware:
    def __init__(self, allowed_roles: Optional[List[UserRole]] = None):
        self.allowed_roles = allowed_roles
    
    async def __call__(self, request: Request):
        try:
            # Get token
            credentials: HTTPAuthorizationCredentials = await security(request)
            token = credentials.credentials
            
            # Verify token and get payload
            payload = verify_token(token)
            user_id = payload.get("sub")
            user_role = payload.get("role")
            
            if not user_id:
                logger.error("No user ID in token payload")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # Check roles if specified
            if self.allowed_roles and user_role not in self.allowed_roles:
                logger.error(f"User role {user_role} not in allowed roles: {self.allowed_roles}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access this resource"
                )
            
            # Get database session
            db = next(get_db())
            
            try:
                # Get user from database
                user = db.query(User).filter(User.id == user_id).first()
                
                if not user:
                    logger.error(f"No user found for ID: {user_id}")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found"
                    )
                
                # Store both user object and payload in request state
                request.state.user = user
                request.state.user_payload = payload
                
                # Return the actual User object
                return user
                
            finally:
                db.close()
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )

# Usage examples - keep these the same
require_auth = AuthMiddleware()
require_recruiter = AuthMiddleware(allowed_roles=[UserRole.RECRUITER])
require_candidate = AuthMiddleware(allowed_roles=[UserRole.CANDIDATE])
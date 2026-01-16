"""
JWT-based tenant extraction middleware.
"""
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from functools import wraps


class TenantMiddleware:
    """Middleware for extracting tenant (ha_id) from JWT tokens."""
    
    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize tenant middleware.
        
        Args:
            secret_key: JWT secret key (defaults to env var)
            algorithm: JWT algorithm
        """
        import os
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY", "your-secret-key")
        self.algorithm = algorithm
        self.security = HTTPBearer()
    
    def extract_tenant_from_token(self, token: str) -> tuple[str, str]:
        """
        Extract ha_id and user_id from JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Tuple of (ha_id, user_id)
            
        Raises:
            HTTPException: If token is invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            ha_id = payload.get("ha_id")
            user_id = payload.get("user_id") or payload.get("sub")
            
            if not ha_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing ha_id claim"
                )
            
            return ha_id, user_id
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    async def get_tenant_from_request(self, request: Request) -> tuple[str, str]:
        """
        Extract tenant from request (JWT token).
        
        Args:
            request: FastAPI request
            
        Returns:
            Tuple of (ha_id, user_id)
        """
        authorization = request.headers.get("Authorization")
        if not authorization:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing Authorization header"
            )
        
        try:
            scheme, token = authorization.split()
            if scheme.lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication scheme"
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Authorization header format"
            )
        
        return self.extract_tenant_from_token(token)


def require_tenant(func):
    """
    Decorator to require tenant (ha_id) in request.
    Injects ha_id and user_id as function parameters.
    """
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        middleware = TenantMiddleware()
        ha_id, user_id = await middleware.get_tenant_from_request(request)
        return await func(request, ha_id=ha_id, user_id=user_id, *args, **kwargs)
    return wrapper

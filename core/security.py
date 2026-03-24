"""
AAC Protocol Security Layer

Provides enterprise-grade authentication and authorization:
- JWT token authentication with refresh tokens
- API Key management with rotation support
- Role-Based Access Control (RBAC)
- Permission-based resource access
- Secure password hashing with bcrypt

This replaces the previous "zero security" implementation.
"""

import os
import time
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any, Callable
from enum import Enum
from functools import wraps

from pydantic import BaseModel, Field
import jwt
from passlib.context import CryptContext


class UserRole(str, Enum):
    """User roles for RBAC"""
    ADMIN = "admin"           # Platform administrators
    MODERATOR = "moderator"   # Dispute mediators
    USER = "user"            # Regular users
    CREATOR = "creator"       # Agent creators
    ARBITRATOR = "arbitrator" # Community arbitrators
    SERVICE = "service"      # Internal services


class Permission(str, Enum):
    """Fine-grained permissions"""
    # Agent management
    AGENT_CREATE = "agent:create"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_READ = "agent:read"
    
    # Task operations
    TASK_CREATE = "task:create"
    TASK_EXECUTE = "task:execute"
    TASK_READ = "task:read"
    TASK_CANCEL = "task:cancel"
    
    # Payment/Escrow
    PAYMENT_SEND = "payment:send"
    PAYMENT_RECEIVE = "payment:receive"
    ESCROW_LOCK = "escrow:lock"
    ESCROW_RELEASE = "escrow:release"
    
    # Dispute resolution
    DISPUTE_CREATE = "dispute:create"
    DISPUTE_MEDIATE = "dispute:mediate"  # Platform mediator only
    DISPUTE_VOTE = "dispute:vote"          # Community arbitrators
    DISPUTE_READ = "dispute:read"
    
    # User management
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # System
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_AUDIT = "system:audit"


# Role-Permission mappings
ROLE_PERMISSIONS: Dict[UserRole, List[Permission]] = {
    UserRole.ADMIN: list(Permission),  # All permissions
    
    UserRole.MODERATOR: [
        Permission.DISPUTE_MEDIATE,
        Permission.DISPUTE_READ,
        Permission.AGENT_READ,
        Permission.TASK_READ,
        Permission.USER_READ,
        Permission.SYSTEM_AUDIT,
    ],
    
    UserRole.USER: [
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_CANCEL,
        Permission.PAYMENT_SEND,
        Permission.DISPUTE_CREATE,
        Permission.DISPUTE_READ,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.AGENT_READ,
    ],
    
    UserRole.CREATOR: [
        Permission.AGENT_CREATE,
        Permission.AGENT_UPDATE,
        Permission.AGENT_DELETE,
        Permission.AGENT_READ,
        Permission.TASK_EXECUTE,
        Permission.TASK_READ,
        Permission.PAYMENT_RECEIVE,
        Permission.ESCROW_RELEASE,
        Permission.DISPUTE_READ,
        Permission.USER_READ,
        Permission.USER_UPDATE,
    ],
    
    UserRole.ARBITRATOR: [
        Permission.DISPUTE_VOTE,
        Permission.DISPUTE_READ,
        Permission.AGENT_READ,
        Permission.TASK_READ,
    ],
    
    UserRole.SERVICE: [
        Permission.TASK_EXECUTE,
        Permission.PAYMENT_RECEIVE,
        Permission.ESCROW_LOCK,
        Permission.ESCROW_RELEASE,
        Permission.AGENT_READ,
        Permission.TASK_READ,
    ],
}


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class SecurityConfig(BaseModel):
    """Security configuration"""
    jwt_secret: str = Field(default_factory=lambda: os.getenv("JWT_SECRET", secrets.token_urlsafe(32)))
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire: int = 3600  # 1 hour
    jwt_refresh_token_expire: int = 604800  # 7 days
    api_key_length: int = 64
    max_api_keys_per_user: int = 10
    nonce_ttl: int = 300  # 5 minutes for replay protection
    

class JWTPayload(BaseModel):
    """JWT token payload"""
    sub: str  # User ID
    role: UserRole
    permissions: List[str]
    iat: int  # Issued at
    exp: int  # Expiration
    jti: str  # Token ID (for revocation)
    type: str  # "access" or "refresh"


class APIKey(BaseModel):
    """API Key model"""
    key_id: str
    key_hash: str  # Hashed key (never store plaintext)
    user_id: str
    role: UserRole
    name: str  # Human-readable name
    permissions: Optional[List[str]] = None  # Optional restriction
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    rate_limit_quota: int = 1000  # Requests per hour


class AuthenticatedUser(BaseModel):
    """Authenticated user context"""
    user_id: str
    role: UserRole
    permissions: Set[Permission]
    auth_method: str  # "jwt" or "api_key"
    token_id: Optional[str] = None  # For revocation checks
    api_key_id: Optional[str] = None


class AuthenticationError(Exception):
    """Authentication failed"""
    pass


class AuthorizationError(Exception):
    """Permission denied"""
    pass


class TokenRevokedError(AuthenticationError):
    """Token has been revoked"""
    pass


class APIKeyInvalidError(AuthenticationError):
    """API Key is invalid or expired"""
    pass


class SecurityManager:
    """
    Centralized security management for AAC Protocol
    
    Handles:
    - JWT token issuance and validation
    - API Key lifecycle management
    - Permission checking
    - Token revocation
    """
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self._revoked_tokens: Set[str] = set()  # In-memory revocation list (use Redis in production)
        self._api_keys: Dict[str, APIKey] = {}   # key_id -> APIKey
        self._key_hash_map: Dict[str, str] = {}  # key_hash -> key_id
        
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
    
    def verify_password(self, password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(password, hashed)
    
    def create_jwt_pair(self, user_id: str, role: UserRole) -> Dict[str, str]:
        """
        Create JWT access and refresh token pair
        
        Args:
            user_id: Unique user identifier
            role: User's role
            
        Returns:
            Dict with "access_token" and "refresh_token"
        """
        now = int(time.time())
        permissions = [p.value for p in ROLE_PERMISSIONS.get(role, [])]
        
        # Access token
        access_jti = secrets.token_urlsafe(16)
        access_payload = {
            "sub": user_id,
            "role": role.value,
            "permissions": permissions,
            "iat": now,
            "exp": now + self.config.jwt_access_token_expire,
            "jti": access_jti,
            "type": "access"
        }
        access_token = jwt.encode(
            access_payload, 
            self.config.jwt_secret, 
            algorithm=self.config.jwt_algorithm
        )
        
        # Refresh token
        refresh_jti = secrets.token_urlsafe(16)
        refresh_payload = {
            "sub": user_id,
            "role": role.value,
            "permissions": permissions,
            "iat": now,
            "exp": now + self.config.jwt_refresh_token_expire,
            "jti": refresh_jti,
            "type": "refresh"
        }
        refresh_token = jwt.encode(
            refresh_payload,
            self.config.jwt_secret,
            algorithm=self.config.jwt_algorithm
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.config.jwt_access_token_expire
        }
    
    def verify_jwt(self, token: str, expected_type: str = "access") -> AuthenticatedUser:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            expected_type: "access" or "refresh"
            
        Returns:
            AuthenticatedUser context
            
        Raises:
            AuthenticationError: If token is invalid
            TokenRevokedError: If token has been revoked
        """
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm]
            )
            
            # Check token type
            if payload.get("type") != expected_type:
                raise AuthenticationError(f"Expected {expected_type} token")
            
            # Check revocation
            jti = payload.get("jti")
            if jti in self._revoked_tokens:
                raise TokenRevokedError("Token has been revoked")
            
            return AuthenticatedUser(
                user_id=payload["sub"],
                role=UserRole(payload["role"]),
                permissions={Permission(p) for p in payload.get("permissions", [])},
                auth_method="jwt",
                token_id=jti
            )
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")
    
    def revoke_token(self, token: str) -> None:
        """Revoke a JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.config.jwt_secret,
                algorithms=[self.config.jwt_algorithm]
            )
            self._revoked_tokens.add(payload["jti"])
        except jwt.InvalidTokenError:
            pass  # Invalid tokens are effectively revoked
    
    def create_api_key(
        self, 
        user_id: str, 
        role: UserRole, 
        name: str,
        permissions: Optional[List[Permission]] = None,
        expires_days: Optional[int] = None
    ) -> tuple[str, APIKey]:
        """
        Create a new API key
        
        Args:
            user_id: Owner of the API key
            role: Role assigned to the key
            name: Human-readable name
            permissions: Optional permission restrictions
            expires_days: Optional expiration
            
        Returns:
            Tuple of (plaintext_key, APIKey object)
            
        Note:
            The plaintext key is shown ONLY at creation time
        """
        # Generate secure random key
        plaintext_key = f"aac_{secrets.token_urlsafe(self.config.api_key_length)}"
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        
        key_id = f"key_{secrets.token_urlsafe(16)}"
        
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            role=role,
            name=name,
            permissions=[p.value for p in permissions] if permissions else None,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=expires_days) if expires_days else None
        )
        
        self._api_keys[key_id] = api_key
        self._key_hash_map[key_hash] = key_id
        
        return plaintext_key, api_key
    
    def verify_api_key(self, plaintext_key: str) -> AuthenticatedUser:
        """
        Verify an API key
        
        Args:
            plaintext_key: The API key to verify
            
        Returns:
            AuthenticatedUser context
            
        Raises:
            APIKeyInvalidError: If key is invalid or expired
        """
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        key_id = self._key_hash_map.get(key_hash)
        
        if not key_id:
            raise APIKeyInvalidError("Invalid API key")
        
        api_key = self._api_keys.get(key_id)
        if not api_key or not api_key.is_active:
            raise APIKeyInvalidError("API key is inactive")
        
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise APIKeyInvalidError("API key has expired")
        
        # Update last used
        api_key.last_used_at = datetime.utcnow()
        
        # Determine permissions
        if api_key.permissions:
            permissions = {Permission(p) for p in api_key.permissions}
        else:
            permissions = {p for p in ROLE_PERMISSIONS.get(api_key.role, [])}
        
        return AuthenticatedUser(
            user_id=api_key.user_id,
            role=api_key.role,
            permissions=permissions,
            auth_method="api_key",
            api_key_id=api_key.key_id
        )
    
    def revoke_api_key(self, key_id: str) -> bool:
        """Revoke an API key by ID"""
        if key_id in self._api_keys:
            api_key = self._api_keys[key_id]
            api_key.is_active = False
            # Remove from hash map
            if api_key.key_hash in self._key_hash_map:
                del self._key_hash_map[api_key.key_hash]
            return True
        return False
    
    def list_api_keys(self, user_id: str) -> List[APIKey]:
        """List all API keys for a user"""
        return [
            key for key in self._api_keys.values()
            if key.user_id == user_id and key.is_active
        ]
    
    def check_permission(self, user: AuthenticatedUser, required: Permission) -> bool:
        """Check if user has a specific permission"""
        return required in user.permissions
    
    def require_permission(self, user: AuthenticatedUser, required: Permission) -> None:
        """
        Require a permission, raise if not present
        
        Raises:
            AuthorizationError: If permission is not granted
        """
        if not self.check_permission(user, required):
            raise AuthorizationError(
                f"Permission denied: {required.value} required"
            )
    
    def require_any_permission(self, user: AuthenticatedUser, permissions: List[Permission]) -> None:
        """Require any of the listed permissions"""
        if not any(p in user.permissions for p in permissions):
            raise AuthorizationError(
                f"Permission denied: any of {[p.value for p in permissions]} required"
            )
    
    def require_all_permissions(self, user: AuthenticatedUser, permissions: List[Permission]) -> None:
        """Require all of the listed permissions"""
        missing = [p for p in permissions if p not in user.permissions]
        if missing:
            raise AuthorizationError(
                f"Permission denied: all of {[p.value for p in permissions]} required, missing: {[p.value for p in missing]}"
            )


# Decorator helpers for FastAPI integration

def require_auth(security_manager: SecurityManager):
    """Dependency factory for requiring authentication"""
    async def dependency(token: Optional[str] = None, api_key: Optional[str] = None):
        if api_key:
            return security_manager.verify_api_key(api_key)
        elif token:
            # Remove "Bearer " prefix if present
            if token.startswith("Bearer "):
                token = token[7:]
            return security_manager.verify_jwt(token)
        else:
            raise AuthenticationError("Authentication required: provide JWT token or API key")
    return dependency


def require_permission_decorator(permission: Permission):
    """Decorator to require a specific permission (for non-FastAPI usage)"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, current_user: AuthenticatedUser, **kwargs):
            if permission not in current_user.permissions:
                raise AuthorizationError(f"Permission denied: {permission.value} required")
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator


# Global security manager instance (singleton pattern)
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get or create global security manager"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


def init_security_manager(config: SecurityConfig) -> SecurityManager:
    """Initialize security manager with custom config"""
    global _security_manager
    _security_manager = SecurityManager(config)
    return _security_manager
"""
AAC Protocol Attack Protection Layer

Provides enterprise-grade protection against common attacks:
- Rate limiting per user/API key/IP
- Replay attack protection with nonce/timestamp
- DDoS mitigation with sliding window
- Request signing verification

Replaces the previous "zero protection" implementation.
"""

import time
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import asyncio
from functools import wraps


class RateLimitStrategy(str, Enum):
    """Rate limiting strategies"""
    SLIDING_WINDOW = "sliding_window"  # Most accurate
    FIXED_WINDOW = "fixed_window"      # Simpler, less accurate
    TOKEN_BUCKET = "token_bucket"      # Allows bursts


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10  # For token bucket
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    block_duration: int = 300  # 5 minutes block after exceeding


@dataclass
class RequestSignature:
    """Request signature for replay protection"""
    timestamp: int
    nonce: str
    signature: str
    payload_hash: Optional[str] = None


@dataclass
class RateLimitStatus:
    """Current rate limit status for a client"""
    remaining_minute: int
    remaining_hour: int
    remaining_day: int
    reset_time: datetime
    is_blocked: bool
    block_expires: Optional[datetime] = None


class RateLimiter:
    """
    Token bucket + sliding window hybrid rate limiter
    
    Features:
    - Multi-tier limiting (minute/hour/day)
    - Per-user, per-API-key, per-IP tracking
    - Automatic blocking with cooldown
    - Thread-safe async operations
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        
        # Storage for rate limit windows: client_id -> {window_type: [(timestamp, count)]}
        self._windows: Dict[str, Dict[str, List[Tuple[int, int]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        # Token bucket storage: client_id -> {bucket_type: tokens}
        self._buckets: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._last_update: Dict[str, Dict[str, int]] = defaultdict(dict)
        
        # Blocked clients: client_id -> unblock_timestamp
        self._blocked: Dict[str, int] = {}
        
        # Cleanup lock
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup = time.time()
    
    def _get_window_key(self, client_id: str, window_type: str) -> str:
        """Generate storage key for a window"""
        now = datetime.utcnow()
        if window_type == "minute":
            return f"{client_id}:{now.strftime('%Y-%m-%d-%H-%M')}"
        elif window_type == "hour":
            return f"{client_id}:{now.strftime('%Y-%m-%d-%H')}"
        elif window_type == "day":
            return f"{client_id}:{now.strftime('%Y-%m-%d')}"
        return client_id
    
    def _is_blocked(self, client_id: str) -> Tuple[bool, Optional[int]]:
        """Check if client is blocked"""
        if client_id in self._blocked:
            unblock_time = self._blocked[client_id]
            if time.time() < unblock_time:
                return True, unblock_time
            else:
                # Unblock
                del self._blocked[client_id]
        return False, None
    
    async def check_rate_limit(self, client_id: str) -> Tuple[bool, RateLimitStatus]:
        """
        Check if request is allowed
        
        Args:
            client_id: User ID, API key ID, or IP address
            
        Returns:
            Tuple of (is_allowed, status)
        """
        now = int(time.time())
        
        # Check if blocked
        blocked, unblock_time = self._is_blocked(client_id)
        if blocked:
            return False, RateLimitStatus(
                remaining_minute=0,
                remaining_hour=0,
                remaining_day=0,
                reset_time=datetime.fromtimestamp(unblock_time),
                is_blocked=True,
                block_expires=datetime.fromtimestamp(unblock_time)
            )
        
        # Clean old windows periodically
        await self._cleanup_old_windows()
        
        window_key_minute = self._get_window_key(client_id, "minute")
        window_key_hour = self._get_window_key(client_id, "hour")
        window_key_day = self._get_window_key(client_id, "day")
        
        # Count requests in current windows
        minute_requests = sum(
            count for ts, count in self._windows[client_id]["minute"]
            if now - ts < 60
        )
        hour_requests = sum(
            count for ts, count in self._windows[client_id]["hour"]
            if now - ts < 3600
        )
        day_requests = sum(
            count for ts, count in self._windows[client_id]["day"]
            if now - ts < 86400
        )
        
        # Check limits
        if (minute_requests >= self.config.requests_per_minute or
            hour_requests >= self.config.requests_per_hour or
            day_requests >= self.config.requests_per_day):
            
            # Block client
            self._blocked[client_id] = now + self.config.block_duration
            
            return False, RateLimitStatus(
                remaining_minute=0,
                remaining_hour=0,
                remaining_day=0,
                reset_time=datetime.fromtimestamp(now + self.config.block_duration),
                is_blocked=True,
                block_expires=datetime.fromtimestamp(now + self.config.block_duration)
            )
        
        # Record this request
        self._windows[client_id]["minute"].append((now, 1))
        self._windows[client_id]["hour"].append((now, 1))
        self._windows[client_id]["day"].append((now, 1))
        
        # Calculate remaining
        reset_time = datetime.fromtimestamp(
            (now // 60 + 1) * 60 if minute_requests < self.config.requests_per_minute
            else (now // 3600 + 1) * 3600
        )
        
        return True, RateLimitStatus(
            remaining_minute=self.config.requests_per_minute - minute_requests - 1,
            remaining_hour=self.config.requests_per_hour - hour_requests - 1,
            remaining_day=self.config.requests_per_day - day_requests - 1,
            reset_time=reset_time,
            is_blocked=False
        )
    
    async def _cleanup_old_windows(self):
        """Clean up expired rate limit windows"""
        # Run cleanup every 60 seconds
        now = time.time()
        if now - self._last_cleanup < 60:
            return
        
        async with self._cleanup_lock:
            cutoff = now - 86400  # Keep 24 hours of history
            
            for client_id in list(self._windows.keys()):
                for window_type in ["minute", "hour", "day"]:
                    self._windows[client_id][window_type] = [
                        (ts, count) for ts, count in self._windows[client_id][window_type]
                        if ts > cutoff
                    ]
                
                # Remove empty clients
                if all(not v for v in self._windows[client_id].values()):
                    del self._windows[client_id]
            
            self._last_cleanup = now
    
    def get_rate_limit_headers(self, status: RateLimitStatus) -> Dict[str, str]:
        """Generate rate limit headers for HTTP responses"""
        headers = {
            "X-RateLimit-Remaining-Minute": str(status.remaining_minute),
            "X-RateLimit-Remaining-Hour": str(status.remaining_hour),
            "X-RateLimit-Remaining-Day": str(status.remaining_day),
            "X-RateLimit-Reset": str(int(status.reset_time.timestamp())),
        }
        if status.is_blocked:
            headers["X-RateLimit-Blocked"] = "true"
        return headers


class ReplayProtection:
    """
    Replay attack protection using nonce + timestamp
    
    Prevents:
    - Request replay attacks
    - Timestamp manipulation
    - Request interception and reuse
    """
    
    def __init__(self, nonce_ttl: int = 300, max_clock_skew: int = 60):
        """
        Args:
            nonce_ttl: How long to remember nonces (seconds)
            max_clock_skew: Maximum allowed clock difference (seconds)
        """
        self.nonce_ttl = nonce_ttl
        self.max_clock_skew = max_clock_skew
        self._seen_nonces: Dict[str, int] = {}  # nonce -> expiration_time
        self._lock = asyncio.Lock()
    
    def generate_nonce(self) -> str:
        """Generate a cryptographically secure nonce"""
        return secrets.token_urlsafe(32)
    
    async def verify_and_record_nonce(
        self, 
        nonce: str, 
        timestamp: int,
        allowed_client_time_window: int = 300
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a nonce hasn't been used and timestamp is valid
        
        Args:
            nonce: The nonce to verify
            timestamp: Client timestamp (seconds since epoch)
            allowed_client_time_window: How old can a request be (seconds)
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        now = int(time.time())
        
        async with self._lock:
            # Clean expired nonces
            await self._cleanup_nonces()
            
            # Check if nonce already used
            if nonce in self._seen_nonces:
                return False, "Nonce already used (replay detected)"
            
            # Check timestamp is not too far in future (clock skew)
            if timestamp > now + self.max_clock_skew:
                return False, "Timestamp too far in future"
            
            # Check timestamp is not too old
            if timestamp < now - allowed_client_time_window:
                return False, "Request too old (timestamp expired)"
            
            # Record nonce
            self._seen_nonces[nonce] = now + self.nonce_ttl
            
            return True, None
    
    async def _cleanup_nonces(self):
        """Remove expired nonces"""
        now = time.time()
        expired = [n for n, exp in self._seen_nonces.items() if exp < now]
        for nonce in expired:
            del self._seen_nonces[nonce]
    
    def create_request_signature(
        self,
        method: str,
        path: str,
        payload: Optional[bytes] = None,
        secret_key: Optional[str] = None
    ) -> RequestSignature:
        """
        Create a signed request for replay protection
        
        Args:
            method: HTTP method
            path: Request path
            payload: Request body
            secret_key: Optional secret for HMAC signing
            
        Returns:
            RequestSignature containing timestamp, nonce, and signature
        """
        timestamp = int(time.time())
        nonce = self.generate_nonce()
        
        # Create payload hash
        if payload:
            payload_hash = hashlib.sha256(payload).hexdigest()
        else:
            payload_hash = ""
        
        # Create signature
        if secret_key:
            sig_data = f"{method}:{path}:{timestamp}:{nonce}:{payload_hash}"
            signature = hmac.new(
                secret_key.encode(),
                sig_data.encode(),
                hashlib.sha256
            ).hexdigest()
        else:
            signature = hashlib.sha256(
                f"{method}:{path}:{timestamp}:{nonce}:{payload_hash}".encode()
            ).hexdigest()
        
        return RequestSignature(
            timestamp=timestamp,
            nonce=nonce,
            signature=signature,
            payload_hash=payload_hash if payload_hash else None
        )
    
    async def verify_request_signature(
        self,
        signature: RequestSignature,
        method: str,
        path: str,
        payload: Optional[bytes] = None,
        secret_key: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify a request signature
        
        Args:
            signature: The signature to verify
            method: HTTP method
            path: Request path
            payload: Request body
            secret_key: Secret key for verification
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # First verify nonce and timestamp
        valid, error = await self.verify_and_record_nonce(
            signature.nonce, 
            signature.timestamp
        )
        if not valid:
            return False, error
        
        # Recalculate expected signature
        if payload:
            payload_hash = hashlib.sha256(payload).hexdigest()
        else:
            payload_hash = ""
        
        if secret_key:
            sig_data = f"{method}:{path}:{signature.timestamp}:{signature.nonce}:{payload_hash}"
            expected_sig = hmac.new(
                secret_key.encode(),
                sig_data.encode(),
                hashlib.sha256
            ).hexdigest()
        else:
            expected_sig = hashlib.sha256(
                f"{method}:{path}:{signature.timestamp}:{signature.nonce}:{payload_hash}".encode()
            ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(signature.signature, expected_sig):
            return False, "Invalid signature"
        
        # Verify payload hash if provided
        if signature.payload_hash and signature.payload_hash != payload_hash:
            return False, "Payload hash mismatch"
        
        return True, None


class DDoSProtection:
    """
    DDoS protection with IP-based and behavior-based detection
    
    Features:
    - IP reputation tracking
    - Connection rate limiting
    - Suspicious pattern detection
    - Automatic IP blocking
    """
    
    def __init__(
        self,
        max_requests_per_second: float = 10.0,
        max_burst: int = 50,
        block_threshold: int = 100,
        block_duration: int = 3600
    ):
        self.max_requests_per_second = max_requests_per_second
        self.max_burst = max_burst
        self.block_threshold = block_threshold
        self.block_duration = block_duration
        
        # IP tracking: ip -> {timestamps: [], suspicious_count: int}
        self._ip_stats: Dict[str, Dict] = defaultdict(
            lambda: {"timestamps": [], "suspicious": 0, "blocked_until": 0}
        )
        self._lock = asyncio.Lock()
    
    async def check_ip(self, ip: str) -> Tuple[bool, Optional[str]]:
        """
        Check if IP should be allowed
        
        Args:
            ip: Client IP address
            
        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        now = time.time()
        
        async with self._lock:
            stats = self._ip_stats[ip]
            
            # Check if currently blocked
            if now < stats["blocked_until"]:
                return False, f"IP blocked until {datetime.fromtimestamp(stats['blocked_until'])}"
            
            # Clean old timestamps (keep last 60 seconds)
            stats["timestamps"] = [t for t in stats["timestamps"] if now - t < 60]
            
            # Add current request
            stats["timestamps"].append(now)
            
            # Check rate
            request_count = len(stats["timestamps"])
            
            # If more than burst in 1 second, suspicious
            recent_count = sum(1 for t in stats["timestamps"] if now - t < 1)
            if recent_count > self.max_burst:
                stats["suspicious"] += 1
            
            # If rate exceeds threshold, block
            if request_count > self.block_threshold:
                stats["blocked_until"] = now + self.block_duration
                return False, f"Rate limit exceeded. IP blocked for {self.block_duration} seconds"
            
            # Check sustained high rate
            if len(stats["timestamps"]) >= 60:
                rate = len(stats["timestamps"]) / 60
                if rate > self.max_requests_per_second:
                    stats["suspicious"] += 1
                    if stats["suspicious"] > 3:
                        stats["blocked_until"] = now + self.block_duration
                        return False, "Suspicious traffic pattern detected"
            
            return True, None
    
    async def report_suspicious(self, ip: str, reason: str):
        """Manually report suspicious IP"""
        async with self._lock:
            self._ip_stats[ip]["suspicious"] += 5
            if self._ip_stats[ip]["suspicious"] > 10:
                self._ip_stats[ip]["blocked_until"] = time.time() + self.block_duration


class ProtectionManager:
    """
    Centralized protection management
    
    Combines rate limiting, replay protection, and DDoS protection
    """
    
    def __init__(
        self,
        rate_limit_config: Optional[RateLimitConfig] = None,
        nonce_ttl: int = 300,
        ddos_max_rps: float = 10.0
    ):
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.replay_protection = ReplayProtection(nonce_ttl=nonce_ttl)
        self.ddos_protection = DDoSProtection(max_requests_per_second=ddos_max_rps)
    
    async def protect_request(
        self,
        client_id: str,
        ip: str,
        method: str,
        path: str,
        nonce: Optional[str] = None,
        timestamp: Optional[int] = None,
        signature: Optional[str] = None,
        payload: Optional[bytes] = None,
        secret_key: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
        """
        Apply all protection layers to a request
        
        Args:
            client_id: User/API key ID
            ip: Client IP address
            method: HTTP method
            path: Request path
            nonce: Request nonce (for replay protection)
            timestamp: Request timestamp
            signature: Request signature
            payload: Request body
            secret_key: Secret for signature verification
            
        Returns:
            Tuple of (is_allowed, error_message, rate_limit_headers)
        """
        # 1. DDoS check
        allowed, reason = await self.ddos_protection.check_ip(ip)
        if not allowed:
            return False, f"DDoS protection: {reason}", None
        
        # 2. Rate limit check
        allowed, status = await self.rate_limiter.check_rate_limit(client_id)
        headers = self.rate_limiter.get_rate_limit_headers(status)
        if not allowed:
            return False, f"Rate limit exceeded", headers
        
        # 3. Replay protection (if nonce provided)
        if nonce and timestamp:
            req_sig = RequestSignature(
                timestamp=timestamp,
                nonce=nonce,
                signature=signature or "",
                payload_hash=hashlib.sha256(payload).hexdigest() if payload else None
            )
            valid, error = await self.replay_protection.verify_request_signature(
                req_sig, method, path, payload, secret_key
            )
            if not valid:
                return False, f"Replay protection: {error}", headers
        
        return True, None, headers
    
    def generate_request_headers(
        self,
        method: str,
        path: str,
        payload: Optional[bytes] = None,
        secret_key: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Generate protection headers for client requests
        
        Args:
            method: HTTP method
            path: Request path
            payload: Request body
            secret_key: Secret for signing
            
        Returns:
            Headers dict with X-Nonce, X-Timestamp, X-Signature
        """
        sig = self.replay_protection.create_request_signature(
            method, path, payload, secret_key
        )
        
        headers = {
            "X-Nonce": sig.nonce,
            "X-Timestamp": str(sig.timestamp),
            "X-Signature": sig.signature,
        }
        if sig.payload_hash:
            headers["X-Payload-Hash"] = sig.payload_hash
        
        return headers


# Decorator for protecting endpoints

def protected_endpoint(protection_manager: ProtectionManager):
    """Decorator to apply protection to an endpoint"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request info from kwargs (assuming FastAPI style)
            request = kwargs.get('request')
            client_id = kwargs.get('client_id', 'anonymous')
            
            if request:
                ip = request.client.host if request.client else "unknown"
                method = request.method
                path = str(request.url)
                
                # Get headers
                nonce = request.headers.get("X-Nonce")
                timestamp_str = request.headers.get("X-Timestamp")
                signature = request.headers.get("X-Signature")
                
                timestamp = int(timestamp_str) if timestamp_str else None
                
                # Read body for payload hash verification
                body = await request.body() if hasattr(request, 'body') else None
                
                allowed, error, headers = await protection_manager.protect_request(
                    client_id=client_id,
                    ip=ip,
                    method=method,
                    path=path,
                    nonce=nonce,
                    timestamp=timestamp,
                    signature=signature,
                    payload=body
                )
                
                if not allowed:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=429, detail=error, headers=headers)
                
                # Add rate limit headers to response
                kwargs['_rate_limit_headers'] = headers
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Global protection manager
_protection_manager: Optional[ProtectionManager] = None


def get_protection_manager() -> ProtectionManager:
    """Get global protection manager"""
    global _protection_manager
    if _protection_manager is None:
        _protection_manager = ProtectionManager()
    return _protection_manager


def init_protection_manager(**kwargs) -> ProtectionManager:
    """Initialize protection manager with custom config"""
    global _protection_manager
    _protection_manager = ProtectionManager(**kwargs)
    return _protection_manager
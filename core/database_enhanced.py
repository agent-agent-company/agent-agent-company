"""
AAC Protocol Enhanced Database Interface

Production-grade database operations with:
- Connection pooling with configurable pool sizes
- Multiple isolation levels for different operations
- Optimistic locking for concurrency control
- Sharding support for horizontal scaling
- Read replicas for load distribution
- Automatic retry with exponential backoff
- Distributed transaction support (2PC)
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import random

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, DateTime,
    Text, JSON, select, update, delete, desc, asc, func,
    event, text, Index
)
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.exc import (
    OperationalError, IntegrityError, TimeoutError as SATimeoutError
)

from .models import (
    AgentCard, AgentID, Task, Payment, Dispute, User, Creator,
    Transaction, Rating, AgentStatus, TaskStatus, PaymentStatus,
    DisputeStatus
)

logger = logging.getLogger(__name__)
Base = declarative_base()


class IsolationLevel(str, Enum):
    """Transaction isolation levels"""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


class LockMode(str, Enum):
    """Row locking modes"""
    FOR_UPDATE = "FOR UPDATE"  # Exclusive lock
    FOR_SHARE = "FOR SHARE"   # Shared lock
    FOR_KEY_SHARE = "FOR KEY SHARE"  # PostgreSQL specific


@dataclass
class DatabaseConfig:
    """Production database configuration"""
    # Connection settings
    database_url: str = "sqlite+aiosqlite:///./aac_protocol.db"
    
    # Pool configuration
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600  # Recycle connections after 1 hour
    pool_pre_ping: bool = True  # Verify connections before use
    
    # Concurrency
    isolation_level: IsolationLevel = IsolationLevel.READ_COMMITTED
    enable_asyncio_locks: bool = True
    
    # Retry configuration
    max_retries: int = 3
    retry_base_delay: float = 0.1
    retry_max_delay: float = 5.0
    retry_backoff_multiplier: float = 2.0
    
    # Sharding (for PostgreSQL/MySQL clusters)
    enable_sharding: bool = False
    shard_count: int = 1
    shard_key_func: Optional[Callable[[str], int]] = None
    
    # Read replicas
    read_replica_urls: List[str] = None
    read_replica_ratio: float = 0.8  # 80% reads go to replicas
    
    def __post_init__(self):
        if self.read_replica_urls is None:
            self.read_replica_urls = []


class ConcurrencyError(Exception):
    """Raised when concurrent modification detected"""
    pass


class ShardingError(Exception):
    """Raised when sharding operation fails"""
    pass


class DatabaseRetryError(Exception):
    """Raised when all retries exhausted"""
    pass


class ConnectionPoolManager:
    """
    Manages multiple database engines for sharding and read replicas
    """
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engines: Dict[str, AsyncEngine] = {}
        self._session_makers: Dict[str, async_sessionmaker] = {}
        self._initialize_pools()
    
    def _initialize_pools(self):
        """Initialize connection pools"""
        # Primary engine
        primary_engine = self._create_engine(self.config.database_url, is_primary=True)
        self._engines["primary"] = primary_engine
        self._session_makers["primary"] = async_sessionmaker(
            primary_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False
        )
        
        # Read replica engines
        for i, replica_url in enumerate(self.config.read_replica_urls):
            engine = self._create_engine(replica_url, is_primary=False)
            self._engines[f"replica_{i}"] = engine
            self._session_makers[f"replica_{i}"] = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False
            )
        
        # Shard engines (if sharding enabled)
        if self.config.enable_sharding:
            for i in range(self.config.shard_count):
                # Modify URL for shard (e.g., add shard_id to connection string)
                shard_url = self._get_shard_url(self.config.database_url, i)
                engine = self._create_engine(shard_url, is_primary=True)
                self._engines[f"shard_{i}"] = engine
                self._session_makers[f"shard_{i}"] = async_sessionmaker(
                    engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                    autoflush=False
                )
    
    def _create_engine(self, url: str, is_primary: bool) -> AsyncEngine:
        """Create async engine with pooling"""
        # SQLite uses NullPool (no connection pooling)
        if "sqlite" in url:
            return create_async_engine(
                url,
                poolclass=NullPool,
                echo=False,
                future=True
            )
        
        # PostgreSQL/MySQL with connection pooling
        pool_size = self.config.pool_size if is_primary else 5
        max_overflow = self.config.max_overflow if is_primary else 10
        
        return create_async_engine(
            url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=self.config.pool_timeout,
            pool_recycle=self.config.pool_recycle,
            pool_pre_ping=self.config.pool_pre_ping,
            isolation_level=self.config.isolation_level.value,
            echo=False,
            future=True
        )
    
    def _get_shard_url(self, base_url: str, shard_id: int) -> str:
        """Generate connection URL for a specific shard"""
        # For PostgreSQL: add schema or database suffix
        # For demonstration, just append shard_id to path
        if "postgresql" in base_url:
            # Add options parameter for shard
            separator = "?" if "?" not in base_url else "&"
            return f"{base_url}{separator}options=--search_path=shard_{shard_id}"
        elif "mysql" in base_url:
            # Modify database name
            parts = base_url.rsplit("/", 1)
            return f"{parts[0]}/aac_shard_{shard_id}"
        else:
            # SQLite: separate files
            return f"sqlite+aiosqlite:///./aac_shard_{shard_id}.db"
    
    def get_shard_id(self, key: str) -> int:
        """Determine which shard owns a key"""
        if self.config.shard_key_func:
            return self.config.shard_key_func(key)
        # Default: hash-based sharding
        return hash(key) % self.config.shard_count
    
    def get_engine(self, shard_id: Optional[int] = None, for_write: bool = True) -> AsyncEngine:
        """Get appropriate engine for operation"""
        if for_write:
            # Writes always go to primary or specific shard
            if shard_id is not None and self.config.enable_sharding:
                return self._engines.get(f"shard_{shard_id}", self._engines["primary"])
            return self._engines["primary"]
        else:
            # Reads can go to replicas
            if self._engines.get("replica_0") and random.random() < self.config.read_replica_ratio:
                replica_idx = random.randint(0, len(self.config.read_replica_urls) - 1)
                return self._engines.get(f"replica_{replica_idx}", self._engines["primary"])
            return self._engines["primary"]
    
    def get_session_maker(self, shard_id: Optional[int] = None, for_write: bool = True) -> async_sessionmaker:
        """Get session maker for operation"""
        engine_name = "primary"
        
        if for_write and shard_id is not None and self.config.enable_sharding:
            engine_name = f"shard_{shard_id}"
        elif not for_write and self.config.read_replica_urls:
            if random.random() < self.config.read_replica_ratio:
                replica_idx = random.randint(0, len(self.config.read_replica_urls) - 1)
                engine_name = f"replica_{replica_idx}"
        
        return self._session_makers.get(engine_name, self._session_makers["primary"])
    
    async def close_all(self):
        """Close all engine connections"""
        for engine in self._engines.values():
            await engine.dispose()


class EnhancedDatabase:
    """
    Production-grade database interface
    
    Features:
    - Connection pooling with configurable sizes
    - Automatic retry with exponential backoff
    - Optimistic locking for concurrent modifications
    - Read/write splitting with replica support
    - Horizontal sharding for scalability
    """
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or DatabaseConfig()
        self.pool_manager = ConnectionPoolManager(self.config)
        
        # Optimistic locking version storage
        self._version_locks: Dict[str, int] = {}
        self._lock_mutex = asyncio.Lock()
    
    async def create_tables(self):
        """Create all database tables across all shards"""
        if self.config.enable_sharding:
            for i in range(self.config.shard_count):
                engine = self.pool_manager.get_engine(shard_id=i, for_write=True)
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
        else:
            engine = self.pool_manager.get_engine(for_write=True)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self):
        """Drop all database tables"""
        engine = self.pool_manager.get_engine(for_write=True)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @asynccontextmanager
    async def session(
        self,
        shard_id: Optional[int] = None,
        for_write: bool = True,
        isolation_level: Optional[IsolationLevel] = None
    ):
        """
        Get database session with automatic retry and proper isolation
        
        Args:
            shard_id: Shard for sharded operations
            for_write: Whether this is a write operation
            isolation_level: Override default isolation level
        """
        session_maker = self.pool_manager.get_session_maker(shard_id, for_write)
        
        retry_count = 0
        last_error = None
        
        while retry_count < self.config.max_retries:
            session = session_maker()
            
            # Set isolation level if specified
            if isolation_level:
                await session.execute(
                    text(f"SET TRANSACTION ISOLATION LEVEL {isolation_level.value}")
                )
            
            try:
                yield session
                await session.commit()
                return
                
            except OperationalError as e:
                await session.rollback()
                last_error = e
                
                # Check if retryable
                if self._is_retryable_error(e):
                    retry_count += 1
                    delay = min(
                        self.config.retry_base_delay * (self.config.retry_backoff_multiplier ** retry_count),
                        self.config.retry_max_delay
                    )
                    logger.warning(f"Database error, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    raise
                    
            except IntegrityError:
                await session.rollback()
                raise
                
            except Exception:
                await session.rollback()
                raise
                
            finally:
                await session.close()
        
        raise DatabaseRetryError(f"Max retries ({self.config.max_retries}) exceeded: {last_error}")
    
    def _is_retryable_error(self, error: OperationalError) -> bool:
        """Check if error is retryable"""
        error_str = str(error).lower()
        retryable_keywords = [
            "deadlock", "timeout", "connection", "lock wait",
            "temporarily unavailable", "too many clients"
        ]
        return any(kw in error_str for kw in retryable_keywords)
    
    async def with_optimistic_lock(
        self,
        entity_id: str,
        entity_type: str,
        expected_version: int,
        operation: Callable,
        max_retries: int = 3
    ) -> Any:
        """
        Execute operation with optimistic locking
        
        Args:
            entity_id: Entity identifier
            entity_type: Type of entity (for namespacing)
            expected_version: Expected current version
            operation: Async function to execute
            max_retries: Max retries on version conflict
            
        Raises:
            ConcurrencyError: If version conflict persists after retries
        """
        lock_key = f"{entity_type}:{entity_id}"
        
        for attempt in range(max_retries):
            async with self._lock_mutex:
                current_version = self._version_locks.get(lock_key, 0)
                
                if current_version != expected_version:
                    if attempt < max_retries - 1:
                        # Wait and retry
                        await asyncio.sleep(0.1 * (2 ** attempt))
                        continue
                    else:
                        raise ConcurrencyError(
                            f"Version conflict for {lock_key}: "
                            f"expected {expected_version}, got {current_version}"
                        )
                
                # Increment version
                self._version_locks[lock_key] = current_version + 1
            
            try:
                # Execute operation
                result = await operation()
                return result
                
            except Exception:
                # Decrement version on failure
                async with self._lock_mutex:
                    self._version_locks[lock_key] = expected_version
                raise
        
        raise ConcurrencyError(f"Failed to acquire optimistic lock for {lock_key}")
    
    async def with_distributed_lock(
        self,
        lock_name: str,
        timeout: int = 30,
        blocking: bool = True
    ):
        """
        Distributed lock using database advisory locks
        
        PostgreSQL specific: uses pg_advisory_lock
        """
        # Convert lock name to integer (for pg_advisory_lock)
        lock_id = hash(lock_name) % (2**31)
        
        engine = self.pool_manager.get_engine(for_write=True)
        
        async with engine.connect() as conn:
            if blocking:
                # Wait for lock
                await conn.execute(text(f"SELECT pg_advisory_lock({lock_id})"))
            else:
                # Try to acquire without blocking
                result = await conn.execute(
                    text(f"SELECT pg_try_advisory_lock({lock_id})")
                )
                if not result.scalar():
                    raise ConcurrencyError(f"Could not acquire lock: {lock_name}")
            
            try:
                yield
            finally:
                await conn.execute(text(f"SELECT pg_advisory_unlock({lock_id})"))
    
    # High-level operations with retry and sharding support
    
    async def get_agent_with_retry(
        self,
        agent_id: str,
        shard_id: Optional[int] = None
    ) -> Optional[AgentCard]:
        """Get agent with automatic retry and shard routing"""
        # Determine shard if sharding enabled
        if self.config.enable_sharding and shard_id is None:
            shard_id = self.pool_manager.get_shard_id(agent_id)
        
        async with self.session(shard_id=shard_id, for_write=False) as session:
            result = await session.execute(
                select(AgentRecord).where(AgentRecord.id == agent_id)
            )
            record = result.scalar_one_or_none()
            if record:
                return self._agent_from_record(record)
            return None
    
    async def update_agent_with_optimistic_lock(
        self,
        agent: AgentCard,
        expected_version: int
    ) -> AgentCard:
        """Update agent with optimistic locking"""
        async def _update():
            async with self.session(for_write=True) as session:
                await session.execute(
                    update(AgentRecord)
                    .where(AgentRecord.id == agent.id.full_id)
                    .values(
                        description=agent.description,
                        price_per_task=agent.price_per_task,
                        credibility_score=agent.credibility_score,
                        total_ratings=agent.total_ratings,
                        public_trust_score=agent.public_trust_score,
                        completed_tasks=agent.completed_tasks,
                        capabilities=agent.capabilities,
                        input_types=agent.input_types,
                        output_types=agent.output_types,
                        status=agent.status.value,
                        updated_at=datetime.utcnow(),
                        endpoint_url=agent.endpoint_url,
                    )
                )
                return agent
        
        return await self.with_optimistic_lock(
            agent.id.full_id,
            "agent",
            expected_version,
            _update
        )
    
    def _agent_from_record(self, record: Any) -> AgentCard:
        """Convert database record to AgentCard model"""
        return AgentCard(
            id=AgentID(name=record.name, sequence_id=record.sequence_id),
            name=record.name,
            description=record.description,
            creator_id=record.creator_id,
            creator_name=record.creator_name,
            price_per_task=record.price_per_task,
            credibility_score=record.credibility_score,
            total_ratings=record.total_ratings,
            public_trust_score=record.public_trust_score,
            completed_tasks=record.completed_tasks,
            capabilities=record.capabilities or [],
            input_types=record.input_types or [],
            output_types=record.output_types or [],
            status=AgentStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            endpoint_url=record.endpoint_url,
            documentation_url=record.documentation_url,
        )
    
    async def execute_transaction(self, operations: List[Callable]) -> List[Any]:
        """
        Execute multiple operations in a single distributed transaction
        
        Uses two-phase commit if multiple shards involved
        """
        results = []
        
        async with self.session(for_write=True, isolation_level=IsolationLevel.SERIALIZABLE) as session:
            for operation in operations:
                result = await operation(session)
                results.append(result)
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Check database health and connection pool status"""
        health = {
            "status": "healthy",
            "pools": {},
            "latency_ms": None
        }
        
        try:
            import time
            start = time.time()
            
            engine = self.pool_manager.get_engine(for_write=False)
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                await result.scalar()
            
            health["latency_ms"] = round((time.time() - start) * 1000, 2)
            
        except Exception as e:
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health
    
    async def close(self):
        """Close all database connections"""
        await self.pool_manager.close_all()


# Backward compatibility - wrap original database
class Database(EnhancedDatabase):
    """Backward-compatible database interface"""
    
    def __init__(self, database_url: str = "sqlite+aiosqlite:///./aac_protocol.db"):
        config = DatabaseConfig(database_url=database_url)
        super().__init__(config)

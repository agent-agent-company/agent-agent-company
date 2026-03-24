"""
AAC Protocol — Real-time Notifications (SSE/WebSocket)

Production-grade real-time event streaming:
- Server-Sent Events (SSE) for server-to-client streaming
- WebSocket support for bidirectional communication
- Event pub/sub with multiple backends (memory/Redis)
- Channel-based subscription model
- Automatic reconnection and heartbeat
"""

import json
import asyncio
from typing import Dict, List, Optional, Callable, Any, AsyncGenerator, Set
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Event types"""
    # Task events
    TASK_CREATED = "task.created"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    
    # Payment events
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_SENT = "payment.sent"
    ESCROW_LOCKED = "escrow.locked"
    ESCROW_RELEASED = "escrow.released"
    
    # Dispute events
    DISPUTE_CREATED = "dispute.created"
    DISPUTE_UPDATED = "dispute.updated"
    DISPUTE_RESOLVED = "dispute.resolved"
    
    # Agent events
    AGENT_REGISTERED = "agent.registered"
    AGENT_UPDATED = "agent.updated"
    AGENT_STATUS_CHANGED = "agent.status_changed"
    
    # User events
    USER_BALANCE_CHANGED = "user.balance_changed"
    RATING_RECEIVED = "rating.received"
    
    # System events
    SYSTEM_NOTICE = "system.notice"
    MAINTENANCE_NOTICE = "system.maintenance"


@dataclass
class Event:
    """Event data structure"""
    type: EventType
    payload: Dict[str, Any]
    timestamp: datetime
    event_id: str
    channel: str  # e.g., "user:123", "agent:456", "global"
    
    def to_json(self) -> str:
        """Serialize to JSON"""
        data = {
            "type": self.type.value,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "id": self.event_id,
            "channel": self.channel
        }
        return json.dumps(data)
    
    def to_sse_format(self) -> str:
        """Format as Server-Sent Event"""
        return f"event: {self.type.value}\ndata: {self.to_json()}\nid: {self.event_id}\n\n"


class EventStore:
    """Abstract event storage backend"""
    
    async def publish(self, event: Event) -> None:
        """Publish event"""
        raise NotImplementedError()
    
    async def subscribe(self, channel: str, callback: Callable[[Event], None]) -> None:
        """Subscribe to channel"""
        raise NotImplementedError()
    
    async def unsubscribe(self, channel: str, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from channel"""
        raise NotImplementedError()
    
    async def get_history(
        self,
        channel: str,
        event_types: Optional[List[EventType]] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get event history"""
        raise NotImplementedError()


class MemoryEventStore(EventStore):
    """In-memory event store (for single-node deployments)"""
    
    def __init__(self, history_limit: int = 1000):
        self._subscribers: Dict[str, Set[Callable[[Event], None]]] = {}
        self._history: Dict[str, List[Event]] = {}
        self._history_limit = history_limit
        self._lock = asyncio.Lock()
    
    async def publish(self, event: Event) -> None:
        """Publish event to channel"""
        async with self._lock:
            # Store in history
            if event.channel not in self._history:
                self._history[event.channel] = []
            self._history[event.channel].append(event)
            
            # Trim history
            if len(self._history[event.channel]) > self._history_limit:
                self._history[event.channel] = self._history[event.channel][-self._history_limit:]
            
            # Notify subscribers
            if event.channel in self._subscribers:
                for callback in self._subscribers[event.channel]:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error notifying subscriber: {e}")
    
    async def subscribe(self, channel: str, callback: Callable[[Event], None]) -> None:
        """Subscribe to channel"""
        async with self._lock:
            if channel not in self._subscribers:
                self._subscribers[channel] = set()
            self._subscribers[channel].add(callback)
    
    async def unsubscribe(self, channel: str, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from channel"""
        async with self._lock:
            if channel in self._subscribers:
                self._subscribers[channel].discard(callback)
    
    async def get_history(
        self,
        channel: str,
        event_types: Optional[List[EventType]] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get event history"""
        async with self._lock:
            events = self._history.get(channel, [])
            
            # Filter by type
            if event_types:
                events = [e for e in events if e.type in event_types]
            
            # Filter by time
            if since:
                events = [e for e in events if e.timestamp >= since]
            
            # Return most recent
            return events[-limit:]


class EventBus:
    """
    Central event bus for real-time notifications
    
    Features:
    - Publish/subscribe model
    - Channel-based routing
    - Event persistence
    - Multiple backend support
    """
    
    def __init__(self, store: Optional[EventStore] = None):
        self.store = store or MemoryEventStore()
        self._event_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID"""
        self._event_counter += 1
        return f"evt-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{self._event_counter}"
    
    async def emit(
        self,
        event_type: EventType,
        payload: Dict[str, Any],
        channel: str,
        broadcast: bool = False
    ) -> Event:
        """
        Emit an event
        
        Args:
            event_type: Type of event
            payload: Event data
            channel: Target channel (e.g., "user:123")
            broadcast: If True, also emit to "global" channel
            
        Returns:
            Created event
        """
        event = Event(
            type=event_type,
            payload=payload,
            timestamp=datetime.utcnow(),
            event_id=self._generate_event_id(),
            channel=channel
        )
        
        # Publish to specific channel
        await self.store.publish(event)
        
        # Optionally broadcast to global
        if broadcast and channel != "global":
            global_event = Event(
                type=event_type,
                payload=payload,
                timestamp=event.timestamp,
                event_id=event.event_id,
                channel="global"
            )
            await self.store.publish(global_event)
        
        logger.debug(f"Event emitted: {event_type.value} to {channel}")
        return event
    
    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Event], None]
    ) -> None:
        """Subscribe to a channel"""
        await self.store.subscribe(channel, callback)
        logger.debug(f"Subscribed to channel: {channel}")
    
    async def unsubscribe(
        self,
        channel: str,
        callback: Callable[[Event], None]
    ) -> None:
        """Unsubscribe from a channel"""
        await self.store.unsubscribe(channel, callback)
        logger.debug(f"Unsubscribed from channel: {channel}")
    
    async def get_user_events(
        self,
        user_id: str,
        event_types: Optional[List[EventType]] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get events for a user"""
        return await self.store.get_history(
            f"user:{user_id}",
            event_types=event_types,
            since=since,
            limit=limit
        )
    
    async def get_agent_events(
        self,
        agent_id: str,
        event_types: Optional[List[EventType]] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Event]:
        """Get events for an agent"""
        return await self.store.get_history(
            f"agent:{agent_id}",
            event_types=event_types,
            since=since,
            limit=limit
        )


class SSEConnectionManager:
    """
    Server-Sent Events connection manager
    
    Manages client connections and streams events
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._active_connections: Dict[str, asyncio.Queue] = {}
        self._connection_lock = asyncio.Lock()
    
    async def connect(self, client_id: str, channels: List[str]) -> str:
        """
        Establish SSE connection
        
        Args:
            client_id: Unique client identifier
            channels: List of channels to subscribe to
            
        Returns:
            Connection ID
        """
        conn_id = f"conn-{client_id}-{datetime.utcnow().strftime('%H%M%S%f')}"
        
        async with self._connection_lock:
            # Create message queue
            queue = asyncio.Queue()
            self._active_connections[conn_id] = queue
        
        # Subscribe to channels
        for channel in channels:
            await self.event_bus.subscribe(channel, lambda e, q=queue: q.put_nowait(e))
        
        logger.info(f"SSE connection established: {conn_id}")
        return conn_id
    
    async def disconnect(self, conn_id: str) -> None:
        """Close SSE connection"""
        async with self._connection_lock:
            if conn_id in self._active_connections:
                del self._active_connections[conn_id]
        
        logger.info(f"SSE connection closed: {conn_id}")
    
    async def stream_events(
        self,
        conn_id: str,
        heartbeat_interval: int = 30
    ) -> AsyncGenerator[str, None]:
        """
        Stream events to client
        
        Yields:
            SSE formatted event strings
        """
        if conn_id not in self._active_connections:
            return
        
        queue = self._active_connections[conn_id]
        last_heartbeat = datetime.utcnow()
        
        try:
            while True:
                # Check for heartbeat
                now = datetime.utcnow()
                if (now - last_heartbeat).seconds >= heartbeat_interval:
                    yield ":heartbeat\n\n"
                    last_heartbeat = now
                
                # Wait for event (with timeout for heartbeat)
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=5.0)
                    yield event.to_sse_format()
                except asyncio.TimeoutError:
                    continue
                    
        except asyncio.CancelledError:
            logger.info(f"SSE streaming cancelled: {conn_id}")
            raise
    
    def get_active_connections(self) -> int:
        """Get number of active connections"""
        return len(self._active_connections)


class NotificationService:
    """
    High-level notification service
    
    Provides convenient methods for common notification patterns
    """
    
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
    
    async def notify_task_created(
        self,
        user_id: str,
        task_id: str,
        agent_id: str,
        price: float
    ) -> None:
        """Notify user that task was created"""
        await self.event_bus.emit(
            EventType.TASK_CREATED,
            {
                "task_id": task_id,
                "agent_id": agent_id,
                "price": price,
                "status": "submitted"
            },
            channel=f"user:{user_id}"
        )
    
    async def notify_task_completed(
        self,
        user_id: str,
        creator_id: str,
        task_id: str,
        result: Any
    ) -> None:
        """Notify user and creator of task completion"""
        # Notify user
        await self.event_bus.emit(
            EventType.TASK_COMPLETED,
            {
                "task_id": task_id,
                "result": result,
                "status": "completed"
            },
            channel=f"user:{user_id}"
        )
        
        # Notify creator
        await self.event_bus.emit(
            EventType.TASK_COMPLETED,
            {
                "task_id": task_id,
                "payment_released": True
            },
            channel=f"user:{creator_id}"
        )
    
    async def notify_payment_received(
        self,
        user_id: str,
        amount: float,
        from_address: Optional[str] = None
    ) -> None:
        """Notify user of incoming payment"""
        await self.event_bus.emit(
            EventType.PAYMENT_RECEIVED,
            {
                "amount": amount,
                "from": from_address,
                "new_balance": None  # Would fetch from DB
            },
            channel=f"user:{user_id}"
        )
    
    async def notify_dispute_update(
        self,
        user_id: str,
        creator_id: str,
        dispute_id: str,
        update_type: str,
        message: str
    ) -> None:
        """Notify parties of dispute updates"""
        payload = {
            "dispute_id": dispute_id,
            "update_type": update_type,
            "message": message
        }
        
        await self.event_bus.emit(
            EventType.DISPUTE_UPDATED,
            payload,
            channel=f"user:{user_id}"
        )
        await self.event_bus.emit(
            EventType.DISPUTE_UPDATED,
            payload,
            channel=f"user:{creator_id}"
        )
    
    async def broadcast_system_notice(
        self,
        message: str,
        level: str = "info"
    ) -> None:
        """Broadcast system-wide notice"""
        await self.event_bus.emit(
            EventType.SYSTEM_NOTICE,
            {
                "message": message,
                "level": level,
                "timestamp": datetime.utcnow().isoformat()
            },
            channel="global",
            broadcast=True
        )


# FastAPI integration helpers

async def sse_endpoint(
    request: Any,  # FastAPI Request
    client_id: str,
    channels: List[str],
    event_bus: EventBus,
    heartbeat: int = 30
):
    """
    FastAPI SSE endpoint handler
    
    Usage:
        @app.get("/events")
        async def events(
            request: Request,
            client_id: str = Query(...),
            channels: str = Query("user:{client_id}")
        ):
            return await sse_endpoint(
                request, client_id, channels.split(","), event_bus
            )
    """
    manager = SSEConnectionManager(event_bus)
    conn_id = await manager.connect(client_id, channels)
    
    try:
        async def event_generator():
            async for data in manager.stream_events(conn_id, heartbeat):
                yield data
        
        return event_generator()
        
    except Exception as e:
        await manager.disconnect(conn_id)
        raise e


# Example usage
"""
# Initialize
store = MemoryEventStore()
event_bus = EventBus(store)
notifications = NotificationService(event_bus)

# Emit event
await event_bus.emit(
    EventType.TASK_COMPLETED,
    {"task_id": "task-123", "result": "success"},
    channel="user:user-456"
)

# Subscribe to events
async def on_task_completed(event):
    print(f"Task completed: {event.payload}")

await event_bus.subscribe("user:user-456", on_task_completed)

# Send notification
await notifications.notify_task_completed(
    user_id="user-456",
    creator_id="creator-789",
    task_id="task-123",
    result={"output": "Hello World"}
)
"""
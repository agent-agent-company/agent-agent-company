"""
AAC Protocol — Task Scheduler & Queue Management

Production-grade task scheduling with:
- Priority queues (urgent, high, normal, low)
- Batch task submission
- Scheduled/delayed tasks
- Task retry with exponential backoff
- Parallel execution control
- Resource limits and rate limiting
"""

import uuid
import asyncio
from typing import List, Optional, Dict, Any, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import heapq
import logging

from ...core.models import Task, TaskInput, TaskStatus, User, AgentCard


logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    """Task priority levels"""
    URGENT = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class QueueStatus(str, Enum):
    """Queue entry status"""
    PENDING = "pending"
    SCHEDULED = "scheduled"  # Will execute at specific time
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class QueuedTask:
    """Task in the queue"""
    task_id: str
    user_id: str
    agent_id: str
    input_data: TaskInput
    priority: TaskPriority
    status: QueueStatus
    created_at: datetime
    scheduled_for: Optional[datetime] = None
    max_retries: int = 3
    retry_count: int = 0
    retry_delay: int = 5  # Base delay in seconds
    callback: Optional[Callable[[Task, str], None]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """For priority queue comparison"""
        # Lower priority number = higher urgency
        # If same priority, earlier scheduled time first
        if self.priority != other.priority:
            return self.priority < other.priority
        
        self_time = self.scheduled_for or self.created_at
        other_time = other.scheduled_for or other.created_at
        return self_time < other_time


@dataclass
class BatchConfig:
    """Batch processing configuration"""
    max_concurrent: int = 5
    batch_size: int = 10
    timeout_per_task: int = 60
    continue_on_error: bool = True
    aggregation_strategy: str = "individual"  # or "merge"


@dataclass
class TaskSchedule:
    """Scheduled task configuration"""
    cron_expression: Optional[str] = None  # e.g., "0 9 * * 1" for weekly Monday 9am
    interval_seconds: Optional[int] = None  # e.g., 3600 for hourly
    run_at: Optional[datetime] = None  # One-time scheduled run
    recurring: bool = False
    end_after: Optional[datetime] = None  # Stop recurring after this time
    max_runs: Optional[int] = None  # Max number of executions


class TaskScheduler:
    """
    Advanced task scheduler with queue management
    
    Features:
    - Priority-based scheduling
    - Delayed/scheduled task execution
    - Batch task processing
    - Automatic retry with backoff
    - Parallel execution control
    """
    
    def __init__(
        self,
        task_executor: Callable[[str, str, TaskInput], Coroutine[Any, Any, Task]],
        max_concurrent: int = 10,
        enable_scheduling: bool = True
    ):
        """
        Initialize scheduler
        
        Args:
            task_executor: Async function to execute a task (user_id, agent_id, input) -> Task
            max_concurrent: Maximum number of concurrent task executions
            enable_scheduling: Whether to enable scheduled/delayed tasks
        """
        self.task_executor = task_executor
        self.max_concurrent = max_concurrent
        self.enable_scheduling = enable_scheduling
        
        # Priority queue (using heapq)
        self._queue: List[QueuedTask] = []
        self._queue_lock = asyncio.Lock()
        
        # Track tasks by ID
        self._tasks: Dict[str, QueuedTask] = {}
        
        # Semaphore for concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)
        
        # Background task for scheduler
        self._scheduler_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks
        self._status_callbacks: Dict[str, List[Callable]] = {}
    
    async def start(self):
        """Start the scheduler"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._process_queue())
        logger.info("Task scheduler started")
    
    async def stop(self):
        """Stop the scheduler gracefully"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Task scheduler stopped")
    
    async def submit_task(
        self,
        user_id: str,
        agent_id: str,
        input_data: TaskInput,
        priority: TaskPriority = TaskPriority.NORMAL,
        delay_seconds: Optional[int] = None,
        schedule: Optional[TaskSchedule] = None,
        max_retries: int = 3,
        callback: Optional[Callable[[Task, str], None]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Submit a task to the queue
        
        Args:
            user_id: Submitting user ID
            agent_id: Target agent ID
            input_data: Task input
            priority: Task priority
            delay_seconds: Delay before execution
            schedule: Optional recurring schedule
            max_retries: Max retry attempts on failure
            callback: Optional callback on completion (task, status)
            metadata: Additional metadata
            
        Returns:
            Task ID
        """
        task_id = f"queued-{uuid.uuid4().hex[:12]}"
        
        scheduled_for = None
        if delay_seconds:
            scheduled_for = datetime.utcnow() + timedelta(seconds=delay_seconds)
        elif schedule and schedule.run_at:
            scheduled_for = schedule.run_at
        
        queued = QueuedTask(
            task_id=task_id,
            user_id=user_id,
            agent_id=agent_id,
            input_data=input_data,
            priority=priority,
            status=QueueStatus.SCHEDULED if scheduled_for else QueueStatus.PENDING,
            created_at=datetime.utcnow(),
            scheduled_for=scheduled_for,
            max_retries=max_retries,
            retry_count=0,
            callback=callback,
            metadata=metadata or {}
        )
        
        async with self._queue_lock:
            heapq.heappush(self._queue, queued)
            self._tasks[task_id] = queued
        
        logger.info(f"Task {task_id} queued with priority {priority.name}")
        return task_id
    
    async def submit_batch(
        self,
        user_id: str,
        tasks: List[Tuple[str, TaskInput]],  # List of (agent_id, input) tuples
        priority: TaskPriority = TaskPriority.NORMAL,
        config: Optional[BatchConfig] = None
    ) -> List[str]:
        """
        Submit multiple tasks as a batch
        
        Args:
            user_id: Submitting user
            tasks: List of (agent_id, input_data) tuples
            priority: Priority for all tasks
            config: Batch processing configuration
            
        Returns:
            List of task IDs
        """
        config = config or BatchConfig()
        task_ids = []
        
        for agent_id, input_data in tasks:
            task_id = await self.submit_task(
                user_id=user_id,
                agent_id=agent_id,
                input_data=input_data,
                priority=priority,
                max_retries=3 if config.continue_on_error else 0
            )
            task_ids.append(task_id)
        
        logger.info(f"Batch submitted: {len(task_ids)} tasks")
        return task_ids
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or scheduled task"""
        async with self._queue_lock:
            if task_id in self._tasks:
                task = self._tasks[task_id]
                if task.status in [QueueStatus.PENDING, QueueStatus.SCHEDULED]:
                    task.status = QueueStatus.CANCELLED
                    logger.info(f"Task {task_id} cancelled")
                    return True
        return False
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get task status and details"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            return {
                "task_id": task_id,
                "status": task.status.value,
                "priority": task.priority.name,
                "created_at": task.created_at.isoformat(),
                "scheduled_for": task.scheduled_for.isoformat() if task.scheduled_for else None,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "metadata": task.metadata
            }
        return None
    
    async def list_user_tasks(
        self,
        user_id: str,
        status: Optional[QueueStatus] = None
    ) -> List[Dict]:
        """List tasks for a user"""
        tasks = []
        async with self._queue_lock:
            for task in self._tasks.values():
                if task.user_id == user_id:
                    if status is None or task.status == status:
                        tasks.append(await self.get_task_status(task.task_id))
        return tasks
    
    async def _process_queue(self):
        """Background task to process the queue"""
        while self._running:
            now = datetime.utcnow()
            
            # Find tasks ready to execute
            ready_tasks = []
            async with self._queue_lock:
                while self._queue:
                    task = self._queue[0]  # Peek
                    
                    # Check if task is ready
                    if task.status == QueueStatus.CANCELLED:
                        heapq.heappop(self._queue)
                        continue
                    
                    if task.scheduled_for and task.scheduled_for > now:
                        # Not ready yet, stop checking (heap is sorted)
                        break
                    
                    if task.status in [QueueStatus.PENDING, QueueStatus.RETRYING]:
                        ready_tasks.append(heapq.heappop(self._queue))
                    else:
                        break
            
            # Execute ready tasks (up to max_concurrent)
            if ready_tasks:
                tasks_to_run = ready_tasks[:self.max_concurrent]
                await asyncio.gather(
                    *[self._execute_task(task) for task in tasks_to_run],
                    return_exceptions=True
                )
            
            # Wait before next check
            await asyncio.sleep(1)
    
    async def _execute_task(self, queued_task: QueuedTask):
        """Execute a single task with retry logic"""
        async with self._semaphore:
            queued_task.status = QueueStatus.PROCESSING
            
            try:
                # Execute
                result = await self.task_executor(
                    queued_task.user_id,
                    queued_task.agent_id,
                    queued_task.input_data
                )
                
                queued_task.status = QueueStatus.COMPLETED
                
                # Invoke callback
                if queued_task.callback:
                    try:
                        queued_task.callback(result, "completed")
                    except:
                        pass
                
                logger.info(f"Task {queued_task.task_id} completed")
                
            except Exception as e:
                logger.error(f"Task {queued_task.task_id} failed: {e}")
                
                # Retry logic
                if queued_task.retry_count < queued_task.max_retries:
                    queued_task.retry_count += 1
                    queued_task.status = QueueStatus.RETRYING
                    
                    # Exponential backoff
                    delay = queued_task.retry_delay * (2 ** queued_task.retry_count)
                    queued_task.scheduled_for = datetime.utcnow() + timedelta(seconds=delay)
                    
                    # Re-queue
                    async with self._queue_lock:
                        heapq.heappush(self._queue, queued_task)
                    
                    logger.info(f"Task {queued_task.task_id} scheduled for retry {queued_task.retry_count}")
                else:
                    queued_task.status = QueueStatus.FAILED
                    
                    # Invoke callback with failure
                    if queued_task.callback:
                        try:
                            queued_task.callback(None, f"failed: {str(e)}")
                        except:
                            pass


class TaskPipeline:
    """
    Task pipeline for chaining multiple agents
    
    Example: Data processing pipeline:
    1. Agent A: Extract text from image
    2. Agent B: Summarize text
    3. Agent C: Translate summary
    """
    
    def __init__(self, scheduler: TaskScheduler):
        self.scheduler = scheduler
        self._steps: List[PipelineStep] = []
    
    def add_step(
        self,
        agent_id: str,
        input_transform: Optional[Callable[[Any], TaskInput]] = None,
        output_transform: Optional[Callable[[TaskOutput], Any]] = None
    ):
        """Add a step to the pipeline"""
        self._steps.append(PipelineStep(
            agent_id=agent_id,
            input_transform=input_transform,
            output_transform=output_transform
        ))
        return self  # For method chaining
    
    async def execute(
        self,
        user_id: str,
        initial_input: TaskInput,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> List[Task]:
        """
        Execute pipeline
        
        Returns:
            List of completed tasks (one per step)
        """
        results = []
        current_input = initial_input
        
        for step in self._steps:
            # Transform input if needed
            if step.input_transform:
                current_input = step.input_transform(current_input)
            
            # Submit task
            task_id = await self.scheduler.submit_task(
                user_id=user_id,
                agent_id=step.agent_id,
                input_data=current_input,
                priority=priority
            )
            
            # Wait for completion (simplified - in production use callbacks)
            while True:
                status = await self.scheduler.get_task_status(task_id)
                if status["status"] in ["completed", "failed"]:
                    break
                await asyncio.sleep(0.5)
            
            # Get result (would fetch from database in real implementation)
            # For now, placeholder
            results.append(None)  # Would be actual task
            
            # Transform output for next step
            if step.output_transform:
                current_input = step.output_transform(None)  # Would use actual output
        
        return results


@dataclass
class PipelineStep:
    """Single step in a pipeline"""
    agent_id: str
    input_transform: Optional[Callable[[Any], TaskInput]] = None
    output_transform: Optional[Callable[[TaskOutput], Any]] = None


class ResourceLimiter:
    """
    Resource limiting for task execution
    
    Limits:
    - Tasks per user per minute
    - Total concurrent tasks
    - Cost per user per day
    """
    
    def __init__(
        self,
        max_tasks_per_user_per_minute: int = 10,
        max_cost_per_user_per_day: float = 100.0
    ):
        self.max_tasks_per_minute = max_tasks_per_user_per_minute
        self.max_cost_per_day = max_cost_per_user_per_day
        
        # Tracking
        self._user_task_counts: Dict[str, List[datetime]] = {}
        self._user_daily_costs: Dict[str, float] = {}
        self._last_reset = datetime.utcnow()
    
    async def check_limits(self, user_id: str, estimated_cost: float) -> Tuple[bool, str]:
        """
        Check if user is within limits
        
        Returns:
            (allowed, reason)
        """
        now = datetime.utcnow()
        
        # Reset daily costs if new day
        if (now - self._last_reset).days >= 1:
            self._user_daily_costs.clear()
            self._last_reset = now
        
        # Check task rate
        if user_id not in self._user_task_counts:
            self._user_task_counts[user_id] = []
        
        # Clean old entries (> 1 minute)
        self._user_task_counts[user_id] = [
            t for t in self._user_task_counts[user_id]
            if (now - t).seconds < 60
        ]
        
        if len(self._user_task_counts[user_id]) >= self.max_tasks_per_minute:
            return False, f"Rate limit exceeded: max {self.max_tasks_per_minute} tasks per minute"
        
        # Check daily cost
        current_cost = self._user_daily_costs.get(user_id, 0.0)
        if current_cost + estimated_cost > self.max_cost_per_day:
            return False, f"Daily cost limit exceeded: ${self.max_cost_per_day}"
        
        # Record
        self._user_task_counts[user_id].append(now)
        self._user_daily_costs[user_id] = current_cost + estimated_cost
        
        return True, "ok"
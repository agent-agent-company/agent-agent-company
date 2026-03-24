"""
AAC Protocol User SDK - Task Management

Task submission, tracking, and management for users.
"""

import uuid
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime, timedelta
import asyncio
import httpx

from ...core.models import (
    Task, TaskInput, TaskOutput, TaskStatus, AgentCard, User,
    Payment, PaymentStatus
)
from ...core.database import Database
from ...core.escrow import EscrowLedger
from .client import DiscoveryClient, AgentSelector, AgentSelectorMode


class TaskError(Exception):
    """Task operation error"""
    pass


class InsufficientFundsError(TaskError):
    """Raised when user has insufficient funds"""
    pass


class TaskManager:
    """
    Manager for task lifecycle
    
    Handles task submission, tracking, and completion.
    """
    
    def __init__(
        self,
        database: Database,
        ledger: EscrowLedger,
        discovery_client: DiscoveryClient
    ):
        self.db = database
        self.ledger = ledger
        self.discovery = discovery_client
        self.selector = AgentSelector(discovery_client)
        self._task_callbacks: Dict[str, Callable] = {}
    
    async def submit_task(
        self,
        user: User,
        agent: AgentCard,
        input_data: TaskInput,
        deadline: Optional[datetime] = None
    ) -> Task:
        """
        Submit task to an agent
        
        Args:
            user: Submitting user
            agent: Target agent
            input_data: Task input
            deadline: Optional deadline
            
        Returns:
            Created task
            
        Raises:
            InsufficientFundsError: If user cannot afford
        """
        # Check balance
        price = agent.price_per_task
        balance = await self.ledger.get_available_balance(user.id)
        
        if balance < price:
            raise InsufficientFundsError(
                f"Insufficient balance: {balance} < {price}"
            )
        
        # Create task
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        
        task = Task(
            id=task_id,
            user_id=user.id,
            agent_id=agent.id.full_id,
            input=input_data,
            price_locked=price,
            status=TaskStatus.SUBMITTED,
            deadline=deadline,
        )
        
        # Save task
        await self.db.create_task(task)
        
        # Lock tokens
        await self.ledger.lock_tokens(user.id, task_id, price)
        
        # Create pending payment
        payment = Payment(
            id=f"payment-{task_id}",
            task_id=task_id,
            from_user_id=user.id,
            to_agent_id=agent.id.full_id,
            to_creator_id=agent.creator_id,
            amount=price,
            status=PaymentStatus.LOCKED,
        )
        await self.db.create_payment(payment)
        
        # Update user stats
        user.total_tasks_submitted += 1
        await self.db.update_user_balance(user.id, user.token_balance)
        
        # Start task processing
        asyncio.create_task(self._process_task(task, agent))
        
        return task
    
    async def submit_with_auto_select(
        self,
        user: User,
        task_description: str,
        mode: AgentSelectorMode = AgentSelectorMode.BALANCED,
        max_price: Optional[float] = None,
        required_capabilities: Optional[list] = None,
        deadline: Optional[datetime] = None
    ) -> Task:
        """
        Auto-select agent and submit task
        
        Args:
            user: Submitting user
            task_description: Task description
            mode: Selection mode
            max_price: Maximum price
            required_capabilities: Required capabilities
            deadline: Deadline
            
        Returns:
            Created task
        """
        from ...core.models import DiscoveryQuery
        
        # Build query
        query = DiscoveryQuery(
            keywords=task_description.lower().split()[:10],
            capabilities=required_capabilities,
            max_price=max_price,
            limit=20,
        )
        
        # Select agent
        agent = await self.selector.select(query, mode)
        
        if not agent:
            raise TaskError("No suitable agent found for task")
        
        # Build task input
        task_input = TaskInput(
            content=task_description,
            metadata={
                "auto_selected": True,
                "selection_mode": mode.value,
            }
        )
        
        # Submit
        return await self.submit_task(user, agent, task_input, deadline)
    
    async def _process_task(self, task: Task, agent: AgentCard):
        """
        Internal task processing
        
        Sends task to agent and handles response.
        """
        try:
            # Update status
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow()
            await self.db.update_task(task)
            
            # Send task to agent via JSON-RPC
            async with httpx.AsyncClient(timeout=300.0) as client:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "task/execute",
                    "params": {
                        "task_id": task.id,
                        "input": task.input.model_dump(),
                    },
                    "id": task.id,
                }
                
                response = await client.post(
                    agent.endpoint_url,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if "result" in result:
                        # Task completed successfully
                        output_data = result["result"]
                        task.output = TaskOutput(
                            content=output_data.get("content", ""),
                            attachments=output_data.get("attachments", []),
                            metadata=output_data.get("metadata", {}),
                        )
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = datetime.utcnow()
                        
                        # Release payment
                        await self._complete_payment(task, agent)
                        
                    elif "error" in result:
                        # Task failed
                        task.status = TaskStatus.FAILED
                        task.error_message = result["error"].get("message", "Unknown error")
                        
                        # Refund user
                        await self._refund_payment(task)
                else:
                    task.status = TaskStatus.FAILED
                    task.error_message = f"Agent returned status {response.status_code}"
                    await self._refund_payment(task)
            
        except httpx.RequestError as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Request failed: {str(e)}"
            await self._refund_payment(task)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = f"Processing error: {str(e)}"
            await self._refund_payment(task)
        
        finally:
            # Save final status
            await self.db.update_task(task)
            
            # Trigger callback if registered
            if task.id in self._task_callbacks:
                try:
                    await self._task_callbacks[task.id](task)
                except Exception:
                    pass
    
    async def _complete_payment(self, task: Task, agent: AgentCard):
        """Complete payment to agent"""
        # Release locked tokens to creator
        await self.ledger.release_payment(
            task_id=task.id,
            user_id=task.user_id,
            creator_id=agent.creator_id,
            agent_id=agent.id.full_id,
            amount=task.price_locked,
        )
        
        # Update payment status
        await self.db.update_payment_status(
            payment_id=f"payment-{task.id}",
            status=PaymentStatus.RELEASED
        )
        
        # Update agent stats
        await self._update_agent_stats(agent.id.full_id)
    
    async def _refund_payment(self, task: Task):
        """Refund payment to user"""
        # Unlock and return tokens
        await self.ledger.unlock_tokens(task.id)
        
        # Update payment status
        await self.db.update_payment_status(
            payment_id=f"payment-{task.id}",
            status=PaymentStatus.REFUNDED
        )
    
    async def _update_agent_stats(self, agent_id: str):
        """Update agent completion stats"""
        agent = await self.db.get_agent(agent_id)
        if agent:
            agent.completed_tasks += 1
            agent.public_trust_score = agent.calculate_trust_score()
            await self.db.update_agent(agent)
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        return await self.db.get_task(task_id)
    
    async def get_user_tasks(
        self,
        user_id: str,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> list:
        """
        Get tasks for a user
        
        Args:
            user_id: User ID
            status: Filter by status
            limit: Maximum results
            
        Returns:
            List of tasks
        """
        # This would query all tasks and filter
        # In production, use database query
        return []
    
    async def cancel_task(self, task_id: str, user_id: str) -> bool:
        """
        Cancel a pending task
        
        Args:
            task_id: Task ID
            user_id: Requesting user
            
        Returns:
            True if cancelled
        """
        task = await self.db.get_task(task_id)
        if not task:
            return False
        
        if task.user_id != user_id:
            raise TaskError("Only the task owner can cancel")
        
        if task.status not in [TaskStatus.PENDING, TaskStatus.SUBMITTED]:
            raise TaskError("Cannot cancel task in current status")
        
        task.status = TaskStatus.CANCELLED
        await self.db.update_task(task)
        
        # Refund
        await self._refund_payment(task)
        
        return True
    
    async def rate_task(
        self,
        task_id: str,
        user_id: str,
        rating: float,
        feedback: Optional[str] = None
    ) -> bool:
        """
        Rate a completed task
        
        Args:
            task_id: Task ID
            user_id: Rating user
            rating: Rating score (1-5)
            feedback: Optional feedback text
            
        Returns:
            True if rated
        """
        task = await self.db.get_task(task_id)
        if not task:
            return False
        
        if task.user_id != user_id:
            raise TaskError("Only the task owner can rate")
        
        if task.status != TaskStatus.COMPLETED:
            raise TaskError("Can only rate completed tasks")
        
        if task.user_rating is not None:
            raise TaskError("Task already rated")
        
        # Save rating
        task.user_rating = rating
        task.user_feedback = feedback
        await self.db.update_task(task)
        
        # Update agent rating
        agent = await self.db.get_agent(task.agent_id)
        if agent:
            agent.update_rating(rating)
            await self.db.update_agent(agent)
        
        return True
    
    def on_task_complete(self, task_id: str, callback: Callable):
        """Register callback for task completion"""
        self._task_callbacks[task_id] = callback


class TaskBuilder:
    """
    Builder for constructing tasks
    
    Provides fluent interface for task creation.
    """
    
    def __init__(self, user: User):
        self._user = user
        self._content: Optional[str] = None
        self._attachments: list = []
        self._metadata: dict = {}
        self._deadline: Optional[datetime] = None
        self._agent: Optional[AgentCard] = None
        self._selection_mode: AgentSelectorMode = AgentSelectorMode.BALANCED
        self._max_price: Optional[float] = None
    
    def with_content(self, content: str) -> "TaskBuilder":
        """Set task content"""
        self._content = content
        return self
    
    def with_attachment(self, attachment: dict) -> "TaskBuilder":
        """Add attachment"""
        self._attachments.append(attachment)
        return self
    
    def with_metadata(self, key: str, value: Any) -> "TaskBuilder":
        """Add metadata"""
        self._metadata[key] = value
        return self
    
    def with_deadline(self, deadline: datetime) -> "TaskBuilder":
        """Set deadline"""
        self._deadline = deadline
        return self
    
    def with_deadline_hours(self, hours: int) -> "TaskBuilder":
        """Set deadline from now"""
        self._deadline = datetime.utcnow() + timedelta(hours=hours)
        return self
    
    def to_agent(self, agent: AgentCard) -> "TaskBuilder":
        """Set target agent"""
        self._agent = agent
        return self
    
    def auto_select(
        self,
        mode: AgentSelectorMode = AgentSelectorMode.BALANCED,
        max_price: Optional[float] = None
    ) -> "TaskBuilder":
        """Enable auto-selection"""
        self._selection_mode = mode
        self._max_price = max_price
        return self
    
    def build(self) -> TaskInput:
        """Build task input"""
        if not self._content:
            raise ValueError("Task content is required")
        
        return TaskInput(
            content=self._content,
            attachments=self._attachments,
            metadata=self._metadata,
        )
    
    async def submit(self, manager: TaskManager) -> Task:
        """Submit task using manager"""
        task_input = self.build()
        
        if self._agent:
            # Use specified agent
            return await manager.submit_task(
                self._user,
                self._agent,
                task_input,
                self._deadline
            )
        else:
            # Auto-select
            return await manager.submit_with_auto_select(
                self._user,
                self._content,
                mode=self._selection_mode,
                max_price=self._max_price,
                deadline=self._deadline,
            )

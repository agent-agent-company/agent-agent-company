"""
AAC Protocol Creator SDK - Agent Base Class

Base class for creating AAC-compatible agents.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

from ...core.models import AgentCard, Task, TaskInput, TaskOutput, TaskStatus
from ...core.rpc import A2AServer, JSONRPCHandler


class AgentCapability:
    """Definition of an agent capability"""
    
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema or {}
        self.output_schema = output_schema or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class Agent(ABC):
    """
    Abstract base class for AAC Protocol agents
    
    Agents must implement the execute_task method and define
    their capabilities.
    """
    
    def __init__(
        self,
        card: AgentCard,
        capabilities: Optional[List[AgentCapability]] = None
    ):
        self.card = card
        self.capabilities = capabilities or []
        self._server: Optional[A2AServer] = None
    
    @abstractmethod
    async def execute_task(self, task_input: TaskInput) -> TaskOutput:
        """
        Execute a task
        
        Args:
            task_input: Task input data
            
        Returns:
            Task output
            
        Raises:
            Exception: If task execution fails
        """
        pass
    
    async def validate_input(self, task_input: TaskInput) -> bool:
        """
        Validate task input before execution
        
        Override to add custom validation.
        
        Args:
            task_input: Task input to validate
            
        Returns:
            True if valid
        """
        return True
    
    async def on_task_start(self, task_id: str, task_input: TaskInput):
        """
        Callback when task starts
        
        Override for initialization.
        """
        pass
    
    async def on_task_complete(
        self,
        task_id: str,
        task_output: TaskOutput,
        duration_ms: float
    ):
        """
        Callback when task completes
        
        Override for cleanup or logging.
        """
        pass
    
    async def on_task_error(self, task_id: str, error: Exception):
        """
        Callback when task fails
        
        Override for error handling.
        """
        pass
    
    async def handle_task_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle task execution request (JSON-RPC handler)
        
        Args:
            params: JSON-RPC params
            
        Returns:
            Task output or error
        """
        task_id = params.get("task_id", "unknown")
        input_data = params.get("input", {})
        
        # Build task input
        task_input = TaskInput(
            content=input_data.get("content", ""),
            attachments=input_data.get("attachments", []),
            metadata=input_data.get("metadata", {}),
        )
        
        # Validate input
        try:
            valid = await self.validate_input(task_input)
            if not valid:
                return {
                    "error": {
                        "code": -32602,
                        "message": "Invalid input",
                    }
                }
        except Exception as e:
            return {
                "error": {
                    "code": -32602,
                    "message": f"Validation error: {str(e)}",
                }
            }
        
        # Execute task
        start_time = datetime.utcnow()
        
        try:
            await self.on_task_start(task_id, task_input)
            
            task_output = await self.execute_task(task_input)
            
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            await self.on_task_complete(task_id, task_output, duration)
            
            return {
                "content": task_output.content,
                "attachments": task_output.attachments,
                "metadata": task_output.metadata,
            }
            
        except Exception as e:
            await self.on_task_error(task_id, e)
            return {
                "error": {
                    "code": -32000,
                    "message": f"Task execution failed: {str(e)}",
                }
            }
    
    def get_card_dict(self) -> Dict[str, Any]:
        """Get agent card as dictionary"""
        return {
            "id": self.card.id.full_id,
            "name": self.card.name,
            "description": self.card.description,
            "creator_id": self.card.creator_id,
            "creator_name": self.card.creator_name,
            "price_per_task": self.card.price_per_task,
            "credibility_score": self.card.credibility_score,
            "public_trust_score": self.card.public_trust_score,
            "capabilities": self.card.capabilities,
            "endpoint_url": self.card.endpoint_url,
        }
    
    def get_capabilities_dict(self) -> List[Dict[str, Any]]:
        """Get capabilities as list of dictionaries"""
        return [cap.to_dict() for cap in self.capabilities]
    
    async def start_server(self, host: str = "0.0.0.0", port: int = 8000):
        """
        Start agent server
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self._server = A2AServer(
            title=f"{self.card.name} Agent",
            version="0.1.0",
            description=self.card.description,
        )
        
        # Register methods
        self._server.register_method("task/execute", self.handle_task_request)
        self._server.register_method("agent/card", lambda p: self.get_card_dict())
        self._server.register_method("agent/capabilities", lambda p: self.get_capabilities_dict())
        
        # Start server
        await self._server.run(host=host, port=port)
    
    async def stop_server(self):
        """Stop agent server"""
        if self._server:
            # Server would be stopped here
            self._server = None


class SimpleAgent(Agent):
    """
    Simple agent implementation with a function-based handler
    
    For quick agent creation without subclassing.
    """
    
    def __init__(
        self,
        card: AgentCard,
        handler: callable,
        capabilities: Optional[List[AgentCapability]] = None
    ):
        super().__init__(card, capabilities)
        self._handler = handler
    
    async def execute_task(self, task_input: TaskInput) -> TaskOutput:
        """Execute using handler function"""
        result = await self._handler(task_input)
        
        if isinstance(result, TaskOutput):
            return result
        elif isinstance(result, str):
            return TaskOutput(content=result)
        elif isinstance(result, dict):
            return TaskOutput(
                content=result.get("content", ""),
                attachments=result.get("attachments", []),
                metadata=result.get("metadata", {}),
            )
        else:
            return TaskOutput(content=str(result))


class EchoAgent(Agent):
    """Example agent that echoes input"""
    
    def __init__(self, creator_id: str):
        from ...core.models import AgentID
        from ...core.models import AgentCard
        
        card = AgentCard(
            id=AgentID(name="echo", sequence_id=1),
            name="Echo Agent",
            description="A simple agent that echoes the input back",
            creator_id=creator_id,
            price_per_task=1.0,
            capabilities=["echo", "test"],
            endpoint_url="http://localhost:8001",
        )
        
        super().__init__(card, [
            AgentCapability("echo", "Echo input back to user")
        ])
    
    async def execute_task(self, task_input: TaskInput) -> TaskOutput:
        """Echo the input"""
        return TaskOutput(
            content=f"Echo: {task_input.content}",
            metadata={
                "original_length": len(task_input.content),
                "has_attachments": len(task_input.attachments) > 0,
            }
        )

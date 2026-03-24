"""
AAC Protocol JSON-RPC Framework

Implements JSON-RPC 2.0 protocol over HTTP using FastAPI.
Based on Google A2A's JSON-RPC implementation.

Features:
- Standard JSON-RPC 2.0 methods
- Async request handling
- Server-Sent Events (SSE) for streaming
- Error handling per spec
"""

import json
import asyncio
from typing import Dict, Any, Optional, Callable, List, Awaitable
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .models import JSONRPCRequest, JSONRPCResponse, JSONRPCError


# JSON-RPC Error Codes
class RPCErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000
    
    # Custom codes
    AGENT_NOT_FOUND = -32101
    INSUFFICIENT_BALANCE = -32102
    TASK_NOT_FOUND = -32103
    PAYMENT_FAILED = -32104
    DISPUTE_ERROR = -32105


class JSONRPCMethod:
    """Decorator for registering JSON-RPC methods"""
    
    def __init__(self, name: str, handler: Callable):
        self.name = name
        self.handler = handler


class JSONRPCHandler:
    """
    JSON-RPC 2.0 Request Handler
    
    Manages method registration and request processing.
    """
    
    def __init__(self):
        self.methods: Dict[str, Callable] = {}
        self.middleware: List[Callable] = []
    
    def register(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    ):
        """
        Register a JSON-RPC method handler
        
        Args:
            name: Method name (e.g., "agent/discover")
            handler: Async function to handle the method
        """
        self.methods[name] = handler
    
    def register_object(self, obj: Any, prefix: str = ""):
        """
        Register all public methods from an object
        
        Args:
            obj: Object with async methods to register
            prefix: Optional prefix for method names
        """
        for name in dir(obj):
            if not name.startswith("_"):
                method = getattr(obj, name)
                if callable(method) and asyncio.iscoroutinefunction(method):
                    method_name = f"{prefix}/{name}" if prefix else name
                    self.register(method_name, method)
    
    async def handle(self, request: JSONRPCRequest) -> JSONRPCResponse:
        """
        Process a JSON-RPC request
        
        Args:
            request: JSON-RPC request object
            
        Returns:
            JSON-RPC response object
        """
        # Validate JSON-RPC version
        if request.jsonrpc != "2.0":
            return self._error_response(
                request.id, RPCErrorCode.INVALID_REQUEST, "Invalid JSON-RPC version"
            )
        
        # Check method exists
        if request.method not in self.methods:
            return self._error_response(
                request.id,
                RPCErrorCode.METHOD_NOT_FOUND,
                f"Method not found: {request.method}"
            )
        
        # Get handler
        handler = self.methods[request.method]
        
        # Execute with error handling
        try:
            params = request.params or {}
            result = await handler(params)
            return JSONRPCResponse(
                jsonrpc="2.0",
                result=result,
                id=request.id
            )
        except TypeError as e:
            return self._error_response(
                request.id, RPCErrorCode.INVALID_PARAMS, str(e)
            )
        except Exception as e:
            return self._error_response(
                request.id, RPCErrorCode.INTERNAL_ERROR, str(e)
            )
    
    def _error_response(
        self,
        request_id: Optional[str],
        code: int,
        message: str,
        data: Any = None
    ) -> JSONRPCResponse:
        """Create error response"""
        error = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error["data"] = data
        
        return JSONRPCResponse(
            jsonrpc="2.0",
            error=error,
            id=request_id
        )
    
    async def handle_batch(
        self,
        requests: List[JSONRPCRequest]
    ) -> List[JSONRPCResponse]:
        """
        Process batch JSON-RPC requests
        
        Args:
            requests: List of JSON-RPC requests
            
        Returns:
            List of JSON-RPC responses
        """
        responses = []
        for request in requests:
            response = await self.handle(request)
            # Only include responses with IDs (notifications don't get responses)
            if request.id is not None:
                responses.append(response)
        return responses


class A2AServer:
    """
    A2A-style JSON-RPC Server using FastAPI
    
    Provides HTTP endpoints for JSON-RPC requests and SSE streaming.
    Similar to Google A2A's server implementation.
    """
    
    def __init__(
        self,
        title: str = "AAC Protocol Server",
        version: str = "0.1.0",
        description: str = "AAC Protocol JSON-RPC API"
    ):
        self.app = FastAPI(
            title=title,
            version=version,
            description=description,
        )
        self.handler = JSONRPCHandler()
        self.streams: Dict[str, asyncio.Queue] = {}  # SSE streams
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.post("/rpc")
        async def rpc_endpoint(request: Request):
            """Main JSON-RPC endpoint"""
            try:
                body = await request.json()
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "error": {
                            "code": RPCErrorCode.PARSE_ERROR,
                            "message": "Parse error"
                        },
                        "id": None
                    }
                )
            
            # Handle batch or single request
            if isinstance(body, list):
                requests = [JSONRPCRequest(**req) for req in body]
                responses = await self.handler.handle_batch(requests)
                return [resp.model_dump() for resp in responses]
            else:
                rpc_request = JSONRPCRequest(**body)
                response = await self.handler.handle(rpc_request)
                return response.model_dump()
        
        @self.app.get("/stream/{task_id}")
        async def stream_endpoint(task_id: str):
            """SSE streaming endpoint for task updates"""
            async def event_generator():
                queue = asyncio.Queue()
                self.streams[task_id] = queue
                
                try:
                    while True:
                        # Wait for updates with timeout
                        try:
                            data = await asyncio.wait_for(queue.get(), timeout=30.0)
                            yield f"data: {json.dumps(data)}\n\n"
                        except asyncio.TimeoutError:
                            # Send keepalive
                            yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                finally:
                    if task_id in self.streams:
                        del self.streams[task_id]
            
            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream"
            )
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
    
    async def send_stream_update(self, task_id: str, data: Dict[str, Any]):
        """
        Send update to SSE stream
        
        Args:
            task_id: Task ID for the stream
            data: Update data to send
        """
        if task_id in self.streams:
            await self.streams[task_id].put(data)
    
    def register_method(
        self,
        name: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    ):
        """Register a JSON-RPC method"""
        self.handler.register(name, handler)
    
    def get_app(self) -> FastAPI:
        """Get FastAPI application instance"""
        return self.app
    
    async def run(self, host: str = "0.0.0.0", port: int = 8000):
        """
        Run the server
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        import uvicorn
        await uvicorn.run(self.app, host=host, port=port)


# Common JSON-RPC methods for AAC Protocol
class AgentMethods:
    """Standard agent methods for JSON-RPC"""
    
    @staticmethod
    async def discover(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Discover available agents
        
        Params:
            - keywords: List of keywords to filter
            - min_credibility: Minimum credibility score
            - max_price: Maximum price
            - limit: Max results (default 20)
        
        Returns:
            List of agent cards
        """
        # Implementation would query database
        return {"agents": []}
    
    @staticmethod
    async def get_card(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get agent card by ID
        
        Params:
            - agent_id: Agent identifier
        
        Returns:
            Agent card or error
        """
        # Implementation would query database
        return {}


class TaskMethods:
    """Standard task methods for JSON-RPC"""
    
    @staticmethod
    async def submit(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit a new task
        
        Params:
            - user_id: User submitting task
            - agent_id: Target agent
            - input: Task input content
            - mode: Selection mode (performance/price/balanced)
        
        Returns:
            Task ID and initial status
        """
        # Implementation would create task
        return {"task_id": "", "status": "pending"}
    
    @staticmethod
    async def get_status(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get task status
        
        Params:
            - task_id: Task identifier
        
        Returns:
            Task status and details
        """
        # Implementation would query task
        return {}
    
    @staticmethod
    async def cancel(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cancel a pending task
        
        Params:
            - task_id: Task identifier
            - user_id: Requesting user
        
        Returns:
            Success or error
        """
        # Implementation would cancel task
        return {"success": True}


class PaymentMethods:
    """Standard payment methods for JSON-RPC"""
    
    @staticmethod
    async def get_balance(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get token balance
        
        Params:
            - address: User or Creator ID
        
        Returns:
            Balance amount
        """
        # Implementation would query balance
        return {"balance": 0.0}
    
    @staticmethod
    async def get_history(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get transaction history
        
        Params:
            - address: User or Creator ID
            - limit: Max transactions (default 50)
        
        Returns:
            List of transactions
        """
        # Implementation would query transactions
        return {"transactions": []}


class DisputeMethods:
    """Standard dispute methods for JSON-RPC"""
    
    @staticmethod
    async def file(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        File a new dispute
        
        Params:
            - task_id: Related task
            - user_id: Filing user
            - claim: Dispute description
            - amount: Claimed amount
        
        Returns:
            Dispute ID
        """
        # Implementation would create dispute
        return {"dispute_id": ""}
    
    @staticmethod
    async def submit_evidence(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submit evidence for dispute
        
        Params:
            - dispute_id: Dispute identifier
            - submitter: User or Agent/Creator ID
            - content: Evidence description
            - attachments: Supporting files
        
        Returns:
            Success status
        """
        # Implementation would add evidence
        return {"success": True}
    
    @staticmethod
    async def get_status(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get dispute status
        
        Params:
            - dispute_id: Dispute identifier
        
        Returns:
            Dispute status and details
        """
        # Implementation would query dispute
        return {}


def create_default_server() -> A2AServer:
    """
    Create a default AAC Protocol server with all standard methods
    
    Returns:
        Configured A2AServer instance
    """
    server = A2AServer()
    
    # Register agent methods
    server.register_method("agent/discover", AgentMethods.discover)
    server.register_method("agent/get_card", AgentMethods.get_card)
    
    # Register task methods
    server.register_method("task/submit", TaskMethods.submit)
    server.register_method("task/get_status", TaskMethods.get_status)
    server.register_method("task/cancel", TaskMethods.cancel)
    
    # Register payment methods
    server.register_method("payment/get_balance", PaymentMethods.get_balance)
    server.register_method("payment/get_history", PaymentMethods.get_history)
    
    # Register dispute methods
    server.register_method("dispute/file", DisputeMethods.file)
    server.register_method("dispute/submit_evidence", DisputeMethods.submit_evidence)
    server.register_method("dispute/get_status", DisputeMethods.get_status)
    
    return server

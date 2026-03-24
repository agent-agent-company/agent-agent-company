"""
AAC Protocol Creator SDK - A2A Server

Server implementation for hosting agents.
"""

from typing import Dict, Any, Optional, List, Callable, Awaitable
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ...core.rpc import A2AServer, JSONRPCHandler, RPCErrorCode
from ...core.models import AgentCard, Task, JSONRPCRequest


class AgentHost:
    """
    Host for multiple agents on a single server
    
    Allows running multiple agents with different endpoints
    on the same server instance.
    """
    
    def __init__(
        self,
        title: str = "AAC Agent Host",
        version: str = "0.1.0",
    ):
        self.app = FastAPI(
            title=title,
            version=version,
            description="Multi-agent hosting server",
        )
        self.agents: Dict[str, AgentCard] = {}
        self.handlers: Dict[str, Callable] = {}
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes"""
        
        @self.app.post("/rpc")
        async def rpc_endpoint(request: Request):
            """Main JSON-RPC endpoint"""
            import json
            
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
            
            # Parse request
            rpc_request = JSONRPCRequest(**body)
            
            # Get agent ID from request if specified
            agent_id = body.get("params", {}).get("agent_id")
            
            # Route to appropriate handler
            if agent_id and agent_id in self.handlers:
                handler = self.handlers[agent_id]
                try:
                    result = await handler(body.get("params", {}))
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": rpc_request.id
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": RPCErrorCode.INTERNAL_ERROR,
                            "message": str(e)
                        },
                        "id": rpc_request.id
                    }
            
            # Try default handler
            method = rpc_request.method
            if method in self.handlers:
                handler = self.handlers[method]
                try:
                    result = await handler(body.get("params", {}))
                    return {
                        "jsonrpc": "2.0",
                        "result": result,
                        "id": rpc_request.id
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": RPCErrorCode.INTERNAL_ERROR,
                            "message": str(e)
                        },
                        "id": rpc_request.id
                    }
            
            # Method not found
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": RPCErrorCode.METHOD_NOT_FOUND,
                    "message": f"Method not found: {method}"
                },
                "id": rpc_request.id
            }
        
        @self.app.get("/agents")
        async def list_agents():
            """List all hosted agents"""
            return {
                "agents": [
                    {
                        "id": agent.id.full_id,
                        "name": agent.name,
                        "description": agent.description,
                        "price": agent.price_per_task,
                        "endpoint": f"/agents/{agent.id.full_id}",
                    }
                    for agent in self.agents.values()
                ]
            }
        
        @self.app.get("/agents/{agent_id}")
        async def get_agent_card(agent_id: str):
            """Get agent card"""
            if agent_id not in self.agents:
                return JSONResponse(
                    status_code=404,
                    content={"error": "Agent not found"}
                )
            
            agent = self.agents[agent_id]
            return {
                "id": agent.id.full_id,
                "name": agent.name,
                "description": agent.description,
                "creator_id": agent.creator_id,
                "price_per_task": agent.price_per_task,
                "credibility_score": agent.credibility_score,
                "public_trust_score": agent.public_trust_score,
                "capabilities": agent.capabilities,
                "endpoint_url": agent.endpoint_url,
            }
        
        @self.app.get("/health")
        async def health_check():
            """Health check"""
            from datetime import datetime
            return {
                "status": "healthy",
                "agents": len(self.agents),
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def register_agent(
        self,
        agent_card: AgentCard,
        task_handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]
    ):
        """
        Register an agent
        
        Args:
            agent_card: Agent card
            task_handler: Handler function for tasks
        """
        self.agents[agent_card.id.full_id] = agent_card
        self.handlers[agent_card.id.full_id] = task_handler
    
    def register_handler(self, method: str, handler: Callable):
        """Register a method handler"""
        self.handlers[method] = handler
    
    def get_app(self) -> FastAPI:
        """Get FastAPI app"""
        return self.app
    
    async def run(self, host: str = "0.0.0.0", port: int = 8000):
        """Run the server"""
        import uvicorn
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


class AgentServer:
    """
    Single agent server
    
    For hosting a single agent with a simplified interface.
    """
    
    def __init__(
        self,
        agent_card: AgentCard,
        task_handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        host: str = "0.0.0.0",
        port: int = 8000
    ):
        self.agent_card = agent_card
        self.task_handler = task_handler
        self.host = host
        self.port = port
        
        self._host = AgentHost(
            title=f"{agent_card.name} Server",
            version="0.1.0",
        )
        self._host.register_agent(agent_card, task_handler)
    
    async def start(self):
        """Start server"""
        await self._host.run(self.host, self.port)
    
    def get_url(self) -> str:
        """Get server URL"""
        return f"http://{self.host}:{self.port}"

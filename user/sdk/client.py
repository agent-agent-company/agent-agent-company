"""
AAC Protocol User SDK - Discovery Client

Client for discovering and selecting agents.
"""

from typing import List, Optional, Dict, Any
import httpx

from ...core.models import AgentCard, AgentID, DiscoveryQuery, AgentSelectorMode


class DiscoveryError(Exception):
    """Discovery operation error"""
    pass


class DiscoveryClient:
    """
    Client for discovering agents from the registry
    
    Supports querying agents by various criteria.
    """
    
    def __init__(self, registry_url: str = "http://localhost:8000"):
        self.registry_url = registry_url
        self._client = httpx.AsyncClient(base_url=registry_url, timeout=30.0)
    
    async def discover(
        self,
        keywords: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        min_credibility: Optional[float] = None,
        min_trust_score: Optional[float] = None,
        max_price: Optional[float] = None,
        sort_by: str = "trust_score",
        limit: int = 20
    ) -> List[AgentCard]:
        """
        Discover agents matching criteria
        
        Args:
            keywords: Search keywords
            capabilities: Required capabilities
            min_credibility: Minimum credibility score (1-5)
            min_trust_score: Minimum trust score (0-100)
            max_price: Maximum price
            sort_by: Sort field (trust_score/price/credibility/name)
            limit: Maximum results
            
        Returns:
            List of matching Agent Cards
        """
        query = DiscoveryQuery(
            keywords=keywords,
            min_credibility=min_credibility,
            min_trust_score=min_trust_score,
            max_price=max_price,
            capabilities=capabilities,
            sort_by=sort_by,
            limit=limit,
        )
        
        # Make JSON-RPC call
        payload = {
            "jsonrpc": "2.0",
            "method": "agent/discover",
            "params": {
                "keywords": query.keywords,
                "min_credibility": query.min_credibility,
                "min_trust_score": query.min_trust_score,
                "max_price": query.max_price,
                "capabilities": query.capabilities,
                "sort_by": query.sort_by,
                "limit": query.limit,
            },
            "id": f"discover-{hash(str(query))}",
        }
        
        try:
            response = await self._client.post("/rpc", json=payload)
            response.raise_for_status()
            
            result = response.json()
            if "error" in result:
                raise DiscoveryError(result["error"]["message"])
            
            # Parse agent cards
            agents = []
            for agent_data in result.get("result", {}).get("agents", []):
                agent_id = AgentID.from_string(agent_data["id"])
                agent = AgentCard(
                    id=agent_id,
                    name=agent_data["name"],
                    description=agent_data.get("description", ""),
                    creator_id=agent_data.get("creator_id", ""),
                    price_per_task=agent_data.get("price_per_task", 0.0),
                    credibility_score=agent_data.get("credibility_score", 3.0),
                    public_trust_score=agent_data.get("public_trust_score", 0.0),
                    capabilities=agent_data.get("capabilities", []),
                    endpoint_url=agent_data.get("endpoint_url", ""),
                )
                agents.append(agent)
            
            return agents
            
        except httpx.RequestError as e:
            raise DiscoveryError(f"Discovery request failed: {e}")
    
    async def get_agent_card(self, agent_id: str) -> Optional[AgentCard]:
        """
        Get full agent card by ID
        
        Args:
            agent_id: Agent identifier
            
        Returns:
            Agent Card or None
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "agent/get_card",
            "params": {"agent_id": agent_id},
            "id": f"card-{agent_id}",
        }
        
        try:
            response = await self._client.post("/rpc", json=payload)
            response.raise_for_status()
            
            result = response.json()
            if "error" in result:
                return None
            
            data = result.get("result", {})
            agent_id_obj = AgentID.from_string(data["id"])
            
            return AgentCard(
                id=agent_id_obj,
                name=data["name"],
                description=data.get("description", ""),
                creator_id=data.get("creator_id", ""),
                creator_name=data.get("creator_name"),
                price_per_task=data.get("price_per_task", 0.0),
                credibility_score=data.get("credibility_score", 3.0),
                total_ratings=data.get("total_ratings", 0),
                public_trust_score=data.get("public_trust_score", 0.0),
                completed_tasks=data.get("completed_tasks", 0),
                capabilities=data.get("capabilities", []),
                input_types=data.get("input_types", []),
                output_types=data.get("output_types", []),
                endpoint_url=data.get("endpoint_url", ""),
                documentation_url=data.get("documentation_url"),
            )
            
        except httpx.RequestError:
            return None
    
    async def find_by_capability(
        self,
        capability: str,
        limit: int = 10
    ) -> List[AgentCard]:
        """
        Find agents with specific capability
        
        Args:
            capability: Capability keyword
            limit: Maximum results
            
        Returns:
            List of matching agents
        """
        return await self.discover(
            capabilities=[capability],
            sort_by="trust_score",
            limit=limit
        )
    
    async def close(self):
        """Close client connection"""
        await self._client.aclose()


class AgentSelector:
    """
    Intelligent agent selector with multiple modes
    
    Modes:
    - PERFORMANCE: Select highest credibility/trust
    - PRICE: Select lowest price
    - BALANCED: Best value (trust/price ratio)
    """
    
    def __init__(self, client: DiscoveryClient):
        self.client = client
    
    async def select(
        self,
        query: DiscoveryQuery,
        mode: AgentSelectorMode = AgentSelectorMode.BALANCED
    ) -> Optional[AgentCard]:
        """
        Select best agent based on mode
        
        Args:
            query: Discovery criteria
            mode: Selection mode
            
        Returns:
            Selected agent or None
        """
        agents = await self.client.discover(
            keywords=query.keywords,
            capabilities=query.capabilities,
            min_credibility=query.min_credibility,
            min_trust_score=query.min_trust_score,
            max_price=query.max_price,
            sort_by="trust_score",
            limit=query.limit,
        )
        
        if not agents:
            return None
        
        if mode == AgentSelectorMode.PERFORMANCE:
            return self._select_by_performance(agents)
        elif mode == AgentSelectorMode.PRICE:
            return self._select_by_price(agents)
        else:  # BALANCED
            return self._select_balanced(agents)
    
    def _select_by_performance(self, agents: List[AgentCard]) -> Optional[AgentCard]:
        """Select agent with highest trust score"""
        return max(agents, key=lambda a: a.public_trust_score) if agents else None
    
    def _select_by_price(self, agents: List[AgentCard]) -> Optional[AgentCard]:
        """Select agent with lowest price"""
        # Filter out agents with price=0 unless all are 0
        priced_agents = [a for a in agents if a.price_per_task > 0]
        if priced_agents:
            return min(priced_agents, key=lambda a: a.price_per_task)
        return agents[0] if agents else None
    
    def _select_balanced(self, agents: List[AgentCard]) -> Optional[AgentCard]:
        """Select agent with best trust-to-price ratio"""
        def score(agent):
            trust = agent.public_trust_score
            price = agent.price_per_task
            
            if price == 0:
                return trust  # Free agents get pure trust score
            
            # Normalize price (assume max reasonable price is 1000)
            normalized_price = min(price / 1000.0, 1.0)
            
            # Score: 70% trust, 30% price efficiency
            return 0.7 * trust + 0.3 * (1.0 - normalized_price) * 100
        
        return max(agents, key=score) if agents else None
    
    async def auto_select(
        self,
        task_description: str,
        max_budget: Optional[float] = None,
        required_capabilities: Optional[List[str]] = None
    ) -> Optional[AgentCard]:
        """
        Auto-select best agent for task
        
        Analyzes task description and requirements to find optimal agent.
        
        Args:
            task_description: Description of the task
            max_budget: Maximum budget
            required_capabilities: Required agent capabilities
            
        Returns:
            Selected agent or None
        """
        # Extract keywords from description (simple approach)
        keywords = task_description.lower().split()[:10]
        
        query = DiscoveryQuery(
            keywords=keywords,
            capabilities=required_capabilities,
            max_price=max_budget,
            sort_by="trust_score",
            limit=20,
        )
        
        # For critical tasks, prefer performance mode
        # For cost-sensitive, prefer price mode
        # Default to balanced
        mode = AgentSelectorMode.BALANCED
        
        return await self.select(query, mode)
    
    def rank_agents(
        self,
        agents: List[AgentCard],
        mode: AgentSelectorMode = AgentSelectorMode.BALANCED
    ) -> List[AgentCard]:
        """
        Rank agents by selection mode
        
        Args:
            agents: List of agents to rank
            mode: Ranking mode
            
        Returns:
            Ranked list
        """
        if mode == AgentSelectorMode.PERFORMANCE:
            return sorted(agents, key=lambda a: a.public_trust_score, reverse=True)
        elif mode == AgentSelectorMode.PRICE:
            return sorted(agents, key=lambda a: a.price_per_task)
        else:  # BALANCED
            def score(agent):
                trust = agent.public_trust_score
                price = max(agent.price_per_task, 1.0)
                return trust / price
            return sorted(agents, key=score, reverse=True)

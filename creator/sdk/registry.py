"""
AAC Protocol Agent Registry

Manages agent registration, discovery, and lifecycle.
"""

import uuid
from typing import List, Optional, Dict, Any, Set
from datetime import datetime

from ...core.models import AgentCard, AgentID, Creator, AgentStatus, DiscoveryQuery
from ...core.database import Database


class RegistryError(Exception):
    """Registry operation error"""
    pass


class DuplicateAgentError(RegistryError):
    """Raised when trying to register duplicate agent"""
    pass


class NameReservationError(RegistryError):
    """Raised when agent name is reserved or already taken"""
    pass


class RegistryClient:
    """
    Client for interacting with the Agent Registry
    
    Handles agent registration, updates, discovery, and management.
    Includes name reservation protection to prevent name squatting and
    ensure globally unique agent identifiers.
    """
    
    # Reserved names that cannot be used (system keywords, offensive terms, etc.)
    RESERVED_NAMES: Set[str] = {
        # System keywords
        "admin", "root", "system", "platform", "official", "support", "help",
        "api", "rpc", "json", "http", "https", "www", "web", "app",
        "test", "testing", "demo", "example", "sample", "template",
        # Protocol keywords
        "aac", "agent", "company", "protocol", "registry", "escrow", "arbitration",
        # Common misleading terms
        "official", "verified", "certified", "trusted", "secure", "safe",
        # Add more as needed
    }
    
    def __init__(self, database: Database):
        self.db = database
        self._name_counters: Dict[str, int] = {}  # In-memory for demo
    
    async def _is_name_available(self, name: str) -> tuple[bool, str]:
        """
        Check if agent name is available for registration.
        
        Args:
            name: Desired agent name
            
        Returns:
            Tuple of (available, reason)
        """
        # Normalize name (lowercase, strip whitespace)
        normalized_name = name.lower().strip()
        
        # Check reserved names
        if normalized_name in self.RESERVED_NAMES:
            return False, f"Name '{name}' is reserved and cannot be used"
        
        # Check minimum length
        if len(normalized_name) < 3:
            return False, "Agent name must be at least 3 characters long"
        
        # Check valid characters (alphanumeric, hyphens, underscores)
        if not all(c.isalnum() or c in '-_' for c in normalized_name):
            return False, "Name can only contain letters, numbers, hyphens, and underscores"
        
        # Check if name is already taken (query database for any agent with this name)
        existing_agents = await self.db.list_agents(limit=1000)
        for agent in existing_agents:
            if agent.id.name.lower() == normalized_name:
                return False, f"Name '{name}' is already registered by another agent"
        
        return True, "OK"
    
    async def register_agent(
        self,
        card: AgentCard,
        creator: Creator
    ) -> AgentCard:
        """
        Register a new agent with name reservation protection.
        
        Args:
            card: Agent Card with metadata
            creator: Creator registering the agent
            
        Returns:
            Registered Agent Card with assigned ID
            
        Raises:
            NameReservationError: If name is reserved or already taken
            DuplicateAgentError: If agent with same ID exists
        """
        # Check name availability (prevents name squatting)
        is_available, reason = await self._is_name_available(card.id.name)
        if not is_available:
            raise NameReservationError(reason)
        
        # Generate sequence ID based on existing agents with same name prefix
        # This ensures uniqueness even if name check somehow missed a collision
        name = card.id.name.lower().strip()
        
        # Query database to find highest existing sequence ID for this name
        existing_agents = await self.db.list_agents(limit=1000)
        max_seq = 0
        for agent in existing_agents:
            if agent.id.name.lower() == name:
                max_seq = max(max_seq, agent.id.sequence_id)
        
        sequence_id = max_seq + 1
        
        # Create final Agent ID
        agent_id = AgentID(name=name, sequence_id=sequence_id)
        
        # Double-check ID doesn't exist
        existing = await self.db.get_agent(agent_id.full_id)
        if existing:
            raise DuplicateAgentError(f"Agent with ID {agent_id.full_id} already exists")
        
        # Update card with assigned ID
        card.id = agent_id
        card.creator_id = creator.id
        card.creator_name = creator.name
        card.created_at = datetime.utcnow()
        card.updated_at = datetime.utcnow()
        
        # Calculate initial trust score
        card.public_trust_score = card.calculate_trust_score()
        
        # Save to database
        await self.db.create_agent(card)
        
        # Update creator's agent list
        if card.id.full_id not in creator.agent_ids:
            creator.agent_ids.append(card.id.full_id)
            await self.db.update_creator(creator)
        
        return card
    
    async def update_agent(
        self,
        card: AgentCard,
        creator: Creator
    ) -> AgentCard:
        """
        Update existing agent
        
        Args:
            card: Updated Agent Card
            creator: Creator making the update
            
        Returns:
            Updated Agent Card
            
        Raises:
            RegistryError: If agent not found or not owned by creator
        """
        # Verify ownership
        existing = await self.db.get_agent(card.id.full_id)
        if not existing:
            raise RegistryError(f"Agent not found: {card.id.full_id}")
        
        if existing.creator_id != creator.id:
            raise RegistryError("Only the creator can update this agent")
        
        # Update fields
        card.updated_at = datetime.utcnow()
        
        # Save update
        await self.db.update_agent(card)
        
        return card
    
    async def deactivate_agent(
        self,
        agent_id: str,
        creator: Creator
    ) -> bool:
        """
        Deactivate an agent
        
        Args:
            agent_id: Agent ID to deactivate
            creator: Creator requesting deactivation
            
        Returns:
            True if successful
        """
        agent = await self.db.get_agent(agent_id)
        if not agent:
            raise RegistryError(f"Agent not found: {agent_id}")
        
        if agent.creator_id != creator.id:
            raise RegistryError("Only the creator can deactivate this agent")
        
        agent.status = AgentStatus.INACTIVE
        await self.db.update_agent(agent)
        
        return True
    
    async def activate_agent(
        self,
        agent_id: str,
        creator: Creator
    ) -> bool:
        """
        Activate a previously deactivated agent
        
        Args:
            agent_id: Agent ID to activate
            creator: Creator requesting activation
            
        Returns:
            True if successful
        """
        agent = await self.db.get_agent(agent_id)
        if not agent:
            raise RegistryError(f"Agent not found: {agent_id}")
        
        if agent.creator_id != creator.id:
            raise RegistryError("Only the creator can activate this agent")
        
        agent.status = AgentStatus.ACTIVE
        await self.db.update_agent(agent)
        
        return True
    
    async def discover_agents(
        self,
        query: Optional[DiscoveryQuery] = None
    ) -> List[AgentCard]:
        """
        Discover agents based on query criteria
        
        Args:
            query: Discovery query parameters
            
        Returns:
            List of matching Agent Cards
        """
        if query is None:
            query = DiscoveryQuery()
        
        # Get all active agents
        agents = await self.db.list_agents(status=AgentStatus.ACTIVE)
        
        # Apply filters
        filtered = []
        for agent in agents:
            # Keyword filter
            if query.keywords:
                agent_text = f"{agent.name} {agent.description} {' '.join(agent.capabilities)}"
                if not any(kw.lower() in agent_text.lower() for kw in query.keywords):
                    continue
            
            # Credibility filter
            if query.min_credibility and agent.credibility_score < query.min_credibility:
                continue
            
            # Trust score filter
            if query.min_trust_score and agent.public_trust_score < query.min_trust_score:
                continue
            
            # Price filter
            if query.max_price is not None and agent.price_per_task > query.max_price:
                continue
            
            # Capabilities filter
            if query.capabilities:
                if not all(cap in agent.capabilities for cap in query.capabilities):
                    continue
            
            filtered.append(agent)
        
        # Sort
        if query.sort_by == "trust_score":
            filtered.sort(key=lambda a: a.public_trust_score, reverse=True)
        elif query.sort_by == "price":
            filtered.sort(key=lambda a: a.price_per_task)
        elif query.sort_by == "credibility":
            filtered.sort(key=lambda a: a.credibility_score, reverse=True)
        elif query.sort_by == "name":
            filtered.sort(key=lambda a: a.name)
        
        # Limit
        return filtered[:query.limit]
    
    async def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        """
        Get agent by ID
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Agent Card or None
        """
        return await self.db.get_agent(agent_id)
    
    async def select_agent(
        self,
        query: DiscoveryQuery,
        mode: str = "balanced"
    ) -> Optional[AgentCard]:
        """
        Select best agent based on mode
        
        Args:
            query: Discovery query
            mode: Selection mode (performance/price/balanced)
            
        Returns:
            Selected Agent Card or None
        """
        agents = await self.discover_agents(query)
        
        if not agents:
            return None
        
        if mode == "performance":
            # Highest trust score
            return max(agents, key=lambda a: a.public_trust_score)
        
        elif mode == "price":
            # Lowest price
            return min(agents, key=lambda a: a.price_per_task)
        
        else:  # balanced
            # Best ratio of trust to price
            def score(agent):
                if agent.price_per_task == 0:
                    return agent.public_trust_score
                return agent.public_trust_score / (agent.price_per_task + 1)
            
            return max(agents, key=score)
    
    async def get_agent_stats(self, agent_id: str) -> Dict[str, Any]:
        """
        Get agent statistics
        
        Args:
            agent_id: Agent ID
            
        Returns:
            Statistics dictionary
        """
        agent = await self.db.get_agent(agent_id)
        if not agent:
            raise RegistryError(f"Agent not found: {agent_id}")
        
        return {
            "agent_id": agent.id.full_id,
            "name": agent.name,
            "status": agent.status.value,
            "price_per_task": agent.price_per_task,
            "credibility_score": agent.credibility_score,
            "total_ratings": agent.total_ratings,
            "public_trust_score": agent.public_trust_score,
            "completed_tasks": agent.completed_tasks,
            "capabilities": agent.capabilities,
            "created_at": agent.created_at.isoformat(),
            "updated_at": agent.updated_at.isoformat(),
        }
    
    async def increment_task_count(self, agent_id: str) -> None:
        """Increment completed task count for agent"""
        agent = await self.db.get_agent(agent_id)
        if agent:
            agent.completed_tasks += 1
            agent.public_trust_score = agent.calculate_trust_score()
            await self.db.update_agent(agent)
    
    async def add_rating(
        self,
        agent_id: str,
        rating: float,
        user_id: str,
        total_tasks: int
    ) -> None:
        """
        Add rating to agent with anti-gaming protections.
        
        Args:
            agent_id: Agent ID
            rating: Rating score (1-5)
            user_id: ID of user giving rating (for tracking unique raters)
            total_tasks: Total tasks completed (for updating stats)
            
        Raises:
            RegistryError: If rating cannot be added (rate limiting, etc.)
        """
        agent = await self.db.get_agent(agent_id)
        if not agent:
            raise RegistryError(f"Agent not found: {agent_id}")
        
        # Check if rating is allowed (rate limiting)
        can_rate, reason = agent.can_receive_rating(user_id)
        if not can_rate:
            raise RegistryError(f"Cannot add rating: {reason}")
        
        # Update rating with user tracking
        agent.update_rating(rating, user_id)
        await self.db.update_agent(agent)


class RegistryServer:
    """
    Server-side registry for managing agent registrations
    
    Provides JSON-RPC methods for agent discovery and management.
    """
    
    def __init__(self, database: Database):
        self.client = RegistryClient(database)
    
    async def agent_discover(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        JSON-RPC method: agent/discover
        
        Discover agents matching criteria.
        """
        query = DiscoveryQuery(
            keywords=params.get("keywords"),
            min_credibility=params.get("min_credibility"),
            min_trust_score=params.get("min_trust_score"),
            max_price=params.get("max_price"),
            capabilities=params.get("capabilities"),
            sort_by=params.get("sort_by", "trust_score"),
            limit=params.get("limit", 20),
        )
        
        agents = await self.client.discover_agents(query)
        
        return {
            "agents": [
                {
                    "id": a.id.full_id,
                    "name": a.name,
                    "description": a.description,
                    "price_per_task": a.price_per_task,
                    "credibility_score": a.credibility_score,
                    "public_trust_score": a.public_trust_score,
                    "capabilities": a.capabilities,
                    "endpoint_url": a.endpoint_url,
                }
                for a in agents
            ],
            "count": len(agents),
        }
    
    async def agent_get_card(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        JSON-RPC method: agent/get_card
        
        Get full agent card by ID.
        """
        agent_id = params.get("agent_id")
        if not agent_id:
            raise ValueError("agent_id is required")
        
        agent = await self.client.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent not found: {agent_id}")
        
        return {
            "id": agent.id.full_id,
            "name": agent.name,
            "description": agent.description,
            "creator_id": agent.creator_id,
            "creator_name": agent.creator_name,
            "price_per_task": agent.price_per_task,
            "credibility_score": agent.credibility_score,
            "total_ratings": agent.total_ratings,
            "public_trust_score": agent.public_trust_score,
            "completed_tasks": agent.completed_tasks,
            "capabilities": agent.capabilities,
            "input_types": agent.input_types,
            "output_types": agent.output_types,
            "status": agent.status.value,
            "endpoint_url": agent.endpoint_url,
            "documentation_url": agent.documentation_url,
        }

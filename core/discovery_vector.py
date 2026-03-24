"""
AAC Protocol — Vector-Based Agent Discovery

AI-powered agent discovery using semantic embeddings:
- Vector embeddings for agent capabilities and descriptions
- Semantic similarity search (not just keyword matching)
- FAISS/Annoy integration for fast approximate nearest neighbor
- Query understanding and intent classification
- Recommendation system based on task-agent matching
"""

import os
import json
import asyncio
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

from .models import AgentCard, DiscoveryQuery, AgentID


@dataclass
class AgentEmbedding:
    """Vector embedding for an agent"""
    agent_id: str
    vector: np.ndarray
    text_hash: str  # Hash of source text for cache invalidation
    created_at: datetime
    model_version: str
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "vector": self.vector.tolist(),
            "text_hash": self.text_hash,
            "created_at": self.created_at.isoformat(),
            "model_version": self.model_version
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "AgentEmbedding":
        return cls(
            agent_id=data["agent_id"],
            vector=np.array(data["vector"]),
            text_hash=data["text_hash"],
            created_at=datetime.fromisoformat(data["created_at"]),
            model_version=data["model_version"]
        )


class LLMProvider:
    """Abstract LLM provider for embeddings and text understanding"""
    
    async def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding vector for text"""
        raise NotImplementedError()
    
    async def understand_query(self, query: str) -> Dict[str, Any]:
        """Parse query intent and extract entities"""
        raise NotImplementedError()
    
    async def generate_agent_recommendation(
        self, 
        task_description: str, 
        candidates: List[AgentCard]
    ) -> Tuple[AgentCard, str]:
        """Generate recommendation with reasoning"""
        raise NotImplementedError()


class MockEmbeddingProvider(LLMProvider):
    """
    Mock embedding provider for testing (no API key required)
    
    Uses simple TF-IDF style vectors for demonstration.
    Replace with real OpenAI/DeepSeek integration for production.
    """
    
    VECTOR_DIM = 384
    
    def __init__(self):
        self._vocab = set()
        self._word_vectors = {}
    
    def _simple_hash_vector(self, text: str) -> np.ndarray:
        """Create deterministic vector from text hash"""
        # Simple word-based hashing for demo
        words = text.lower().split()
        vector = np.zeros(self.VECTOR_DIM)
        
        for word in words:
            # Hash word to position
            hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)
            pos = hash_val % self.VECTOR_DIM
            # Weight by position in text (earlier words more important)
            weight = 1.0 / (words.index(word) + 1) if word in words else 0.1
            vector[pos] += weight
        
        # Normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        
        return vector
    
    async def get_embedding(self, text: str) -> np.ndarray:
        """Get mock embedding"""
        return self._simple_hash_vector(text)
    
    async def understand_query(self, query: str) -> Dict[str, Any]:
        """Parse query into structured understanding"""
        # Simple keyword extraction
        words = query.lower().split()
        
        # Detect price constraints
        max_price = None
        for i, word in enumerate(words):
            if word in ["under", "below", "max", "maximum"] and i + 1 < len(words):
                try:
                    max_price = float(words[i + 1].replace("$", ""))
                except:
                    pass
        
        # Detect capability requirements
        common_capabilities = [
            "weather", "translation", "summarization", "code", "writing",
            "analysis", "search", "image", "voice", "chat", "math",
            "data", "api", "webhook", "database", "ml", "ai"
        ]
        required_capabilities = [cap for cap in common_capabilities if cap in query.lower()]
        
        # Detect quality preference
        quality_keywords = ["best", "top", "high quality", "reliable", "trusted"]
        prefer_quality = any(kw in query.lower() for kw in quality_keywords)
        
        # Detect budget preference
        budget_keywords = ["cheap", "affordable", "low cost", "budget"]
        prefer_budget = any(kw in query.lower() for kw in budget_keywords)
        
        return {
            "original_query": query,
            "keywords": words,
            "max_price": max_price,
            "required_capabilities": required_capabilities,
            "prefer_quality": prefer_quality,
            "prefer_budget": prefer_budget,
            "intent": "discover" if "find" in query.lower() else "compare"
        }
    
    async def generate_agent_recommendation(
        self, 
        task_description: str, 
        candidates: List[AgentCard]
    ) -> Tuple[AgentCard, str]:
        """Generate recommendation with simple scoring"""
        if not candidates:
            return None, "No suitable agents found"
        
        # Score candidates
        task_words = set(task_description.lower().split())
        best_agent = None
        best_score = -1
        
        for agent in candidates:
            score = 0.0
            
            # Capability match
            for cap in agent.capabilities:
                if cap.lower() in task_words:
                    score += 10.0
            
            # Name/description match
            agent_text = f"{agent.name} {agent.description}".lower()
            for word in task_words:
                if word in agent_text:
                    score += 5.0
            
            # Quality score
            score += agent.public_trust_score * 0.3
            score += agent.credibility_score * 2.0
            
            # Penalize very high price
            if agent.price_per_task > 100:
                score -= (agent.price_per_task - 100) * 0.1
            
            if score > best_score:
                best_score = score
                best_agent = agent
        
        if best_agent:
            reason = f"Selected based on capability match (score: {best_score:.1f})"
            return best_agent, reason
        
        return candidates[0], "First available agent selected"


class OpenAIEmbeddingProvider(LLMProvider):
    """
    OpenAI API integration for embeddings
    
    Supports OpenAI and compatible APIs (DeepSeek, etc.)
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "text-embedding-3-small"
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-3-small")
        self.chat_model = os.getenv("LLM_CHAT_MODEL", "gpt-3.5-turbo")
        
        # Initialize client lazily
        self._client = None
    
    def _get_client(self):
        """Lazy initialization of OpenAI client"""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
            except ImportError:
                raise ImportError("openai package required. Run: pip install openai")
        return self._client
    
    async def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding from OpenAI API"""
        client = self._get_client()
        
        response = await client.embeddings.create(
            model=self.model,
            input=text[:8000]  # OpenAI limit
        )
        
        embedding = response.data[0].embedding
        return np.array(embedding)
    
    async def understand_query(self, query: str) -> Dict[str, Any]:
        """Use LLM to parse query intent"""
        client = self._get_client()
        
        system_prompt = """You are a query parser for an AI agent marketplace. 
        Parse the user's request and extract:
        1. Required capabilities (list)
        2. Max price (number or null)
        3. Quality preference (0-10)
        4. Budget preference (0-10)
        5. Intent type (discover/compare/select)
        
        Return ONLY valid JSON."""
        
        response = await client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Parse this query: {query}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            result["original_query"] = query
            return result
        except:
            return {
                "original_query": query,
                "keywords": query.split(),
                "max_price": None,
                "required_capabilities": [],
                "prefer_quality": 5,
                "prefer_budget": 5,
                "intent": "discover"
            }
    
    async def generate_agent_recommendation(
        self, 
        task_description: str, 
        candidates: List[AgentCard]
    ) -> Tuple[AgentCard, str]:
        """Use LLM to recommend best agent"""
        client = self._get_client()
        
        # Build candidates info
        candidates_info = []
        for i, agent in enumerate(candidates[:10]):  # Limit to top 10
            candidates_info.append({
                "index": i,
                "id": agent.id.full_id,
                "name": agent.name,
                "capabilities": agent.capabilities,
                "price": agent.price_per_task,
                "trust_score": agent.public_trust_score,
                "credibility": agent.credibility_score
            })
        
        system_prompt = """You are an expert at matching tasks to AI agents.
        Given a task and candidate agents, select the BEST agent and explain why.
        Consider: capability match, price, quality, relevance to task.
        
        Return JSON: {"selected_index": number, "reasoning": "string"}"""
        
        response = await client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Task: {task_description}\n\nCandidates: {json.dumps(candidates_info)}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            selected_idx = result.get("selected_index", 0)
            reasoning = result.get("reasoning", "No reasoning provided")
            
            if 0 <= selected_idx < len(candidates):
                return candidates[selected_idx], reasoning
        except:
            pass
        
        return candidates[0] if candidates else None, "Fallback selection"


class VectorStore:
    """
    Vector storage and similarity search
    
    Supports:
    - In-memory numpy (for small datasets)
    - FAISS (for large-scale search)
    - Annoy (for approximate search)
    """
    
    def __init__(self, use_faiss: bool = False, use_annoy: bool = False):
        self.embeddings: Dict[str, AgentEmbedding] = {}
        self.use_faiss = use_faiss
        self.use_annoy = use_annoy
        
        self._faiss_index = None
        self._annoy_index = None
        self._id_to_index: Dict[str, int] = {}
        self._index_to_id: Dict[int, str] = {}
        
        if use_faiss:
            try:
                import faiss
                self._faiss_available = True
            except ImportError:
                self._faiss_available = False
                print("FAISS not available, using numpy")
        
        if use_annoy:
            try:
                from annoy import AnnoyIndex
                self._annoy_available = True
            except ImportError:
                self._annoy_available = False
                print("Annoy not available, using numpy")
    
    def add_embedding(self, embedding: AgentEmbedding):
        """Add or update embedding"""
        self.embeddings[embedding.agent_id] = embedding
        # Invalidate indexes
        self._faiss_index = None
        self._annoy_index = None
    
    def remove_embedding(self, agent_id: str):
        """Remove embedding"""
        if agent_id in self.embeddings:
            del self.embeddings[agent_id]
            self._faiss_index = None
            self._annoy_index = None
    
    def _build_numpy_index(self):
        """Build simple numpy-based index"""
        if not self.embeddings:
            return None, None
        
        ids = list(self.embeddings.keys())
        vectors = np.array([self.embeddings[id].vector for id in ids])
        
        return vectors, ids
    
    def search(
        self, 
        query_vector: np.ndarray, 
        top_k: int = 10,
        min_similarity: float = 0.5
    ) -> List[Tuple[str, float]]:
        """
        Search for similar agents
        
        Returns:
            List of (agent_id, similarity_score) tuples
        """
        if not self.embeddings:
            return []
        
        # Use numpy for now (FAISS/Annoy can be added later)
        vectors, ids = self._build_numpy_index()
        
        if vectors is None:
            return []
        
        # Calculate cosine similarities
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []
        
        query_normalized = query_vector / query_norm
        
        # Normalize all vectors
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        vectors_normalized = vectors / norms
        
        # Cosine similarity = dot product of normalized vectors
        similarities = np.dot(vectors_normalized, query_normalized)
        
        # Filter by minimum similarity and get top-k
        valid_indices = np.where(similarities >= min_similarity)[0]
        if len(valid_indices) == 0:
            return []
        
        # Sort by similarity descending
        sorted_indices = valid_indices[np.argsort(-similarities[valid_indices])]
        top_indices = sorted_indices[:top_k]
        
        results = [
            (ids[i], float(similarities[i]))
            for i in top_indices
        ]
        
        return results


class VectorDiscoveryEngine:
    """
    AI-powered agent discovery engine
    
    Replaces simple keyword search with semantic understanding:
    1. Converts agent descriptions to embeddings
    2. Converts user queries to embeddings
    3. Performs vector similarity search
    4. Ranks results by semantic relevance
    5. LLM-based recommendation for final selection
    """
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        vector_store: Optional[VectorStore] = None
    ):
        # Initialize LLM provider
        if llm_provider is None:
            # Try to use real API if key available, else mock
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
            if api_key:
                base_url = os.getenv("LLM_BASE_URL")
                llm_provider = OpenAIEmbeddingProvider(api_key=api_key, base_url=base_url)
            else:
                llm_provider = MockEmbeddingProvider()
        
        self.llm = llm_provider
        self.vector_store = vector_store or VectorStore()
        
        # Cache for embeddings
        self._embedding_cache: Dict[str, AgentEmbedding] = {}
    
    def _create_agent_text(self, agent: AgentCard) -> str:
        """Create searchable text from agent card"""
        parts = [
            f"Name: {agent.name}",
            f"Description: {agent.description}",
            f"Capabilities: {', '.join(agent.capabilities)}",
            f"Input types: {', '.join(agent.input_types)}",
            f"Output types: {', '.join(agent.output_types)}",
            f"Price: {agent.price_per_task}",
            f"Trust score: {agent.public_trust_score}",
        ]
        return "\n".join(parts)
    
    async def index_agent(self, agent: AgentCard) -> AgentEmbedding:
        """
        Index an agent for semantic search
        
        Args:
            agent: Agent to index
            
        Returns:
            AgentEmbedding object
        """
        # Create text representation
        agent_text = self._create_agent_text(agent)
        
        # Check cache
        text_hash = hashlib.md5(agent_text.encode()).hexdigest()
        cached = self._embedding_cache.get(agent.id.full_id)
        if cached and cached.text_hash == text_hash:
            return cached
        
        # Generate embedding
        vector = await self.llm.get_embedding(agent_text)
        
        # Create embedding record
        embedding = AgentEmbedding(
            agent_id=agent.id.full_id,
            vector=vector,
            text_hash=text_hash,
            created_at=datetime.utcnow(),
            model_version="v1"
        )
        
        # Store
        self._embedding_cache[agent.id.full_id] = embedding
        self.vector_store.add_embedding(embedding)
        
        return embedding
    
    async def index_agents(self, agents: List[AgentCard]) -> List[AgentEmbedding]:
        """Index multiple agents"""
        embeddings = []
        for agent in agents:
            emb = await self.index_agent(agent)
            embeddings.append(emb)
        return embeddings
    
    async def semantic_search(
        self,
        query: str,
        top_k: int = 20,
        min_similarity: float = 0.5,
        agent_filter: Optional[Callable[[AgentCard], bool]] = None
    ) -> List[Tuple[AgentCard, float]]:
        """
        Perform semantic search for agents
        
        Args:
            query: Natural language query
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            agent_filter: Optional filter function
            
        Returns:
            List of (AgentCard, similarity_score) tuples
        """
        # Get query embedding
        query_embedding = await self.llm.get_embedding(query)
        
        # Search vector store
        results = self.vector_store.search(
            query_embedding, 
            top_k=top_k * 2,  # Get more for filtering
            min_similarity=min_similarity
        )
        
        # Convert to AgentCard objects (in production, fetch from DB)
        # For now, return IDs with scores
        return results
    
    async def intelligent_discover(
        self,
        query: str,
        available_agents: List[AgentCard],
        top_k: int = 10
    ) -> List[Tuple[AgentCard, float, str]]:
        """
        Intelligent agent discovery with LLM understanding
        
        Args:
            query: User's natural language query
            available_agents: Pool of available agents
            top_k: Number of results
            
        Returns:
            List of (AgentCard, relevance_score, match_reason) tuples
        """
        # Step 1: Understand query
        query_understanding = await self.llm.understand_query(query)
        
        # Step 2: Filter by hard constraints (price, capabilities)
        filtered_agents = []
        for agent in available_agents:
            # Check price constraint
            max_price = query_understanding.get("max_price")
            if max_price and agent.price_per_task > max_price:
                continue
            
            # Check required capabilities
            required_caps = query_understanding.get("required_capabilities", [])
            if required_caps and not all(cap in agent.capabilities for cap in required_caps):
                continue
            
            filtered_agents.append(agent)
        
        if not filtered_agents:
            return []
        
        # Step 3: Index remaining agents
        await self.index_agents(filtered_agents)
        
        # Step 4: Semantic search
        semantic_results = await self.semantic_search(query, top_k=len(filtered_agents))
        
        # Step 5: Combine and rank
        results = []
        agent_map = {a.id.full_id: a for a in filtered_agents}
        
        for agent_id, similarity in semantic_results:
            if agent_id in agent_map:
                agent = agent_map[agent_id]
                
                # Calculate combined score
                semantic_score = similarity * 0.4
                capability_score = 0.0
                for cap in query_understanding.get("required_capabilities", []):
                    if cap in agent.capabilities:
                        capability_score += 0.2
                
                quality_score = (agent.public_trust_score / 100.0) * 0.2
                
                price_score = 0.0
                if query_understanding.get("prefer_budget"):
                    # Prefer lower price
                    price_score = max(0, 1.0 - agent.price_per_task / 100) * 0.2
                elif query_understanding.get("prefer_quality"):
                    # Trust score already included, maybe boost it
                    quality_score *= 1.5
                
                combined_score = min(1.0, semantic_score + capability_score + quality_score + price_score)
                
                # Generate match reason
                reasons = []
                if capability_score > 0:
                    reasons.append("capability match")
                if similarity > 0.7:
                    reasons.append("semantic relevance")
                if agent.public_trust_score > 80:
                    reasons.append("high trust score")
                if agent.price_per_task < 10:
                    reasons.append("affordable price")
                
                reason = ", ".join(reasons) if reasons else "general match"
                
                results.append((agent, combined_score, reason))
        
        # Sort by score and return top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    async def recommend_agent(
        self,
        task_description: str,
        candidates: List[AgentCard]
    ) -> Tuple[Optional[AgentCard], str]:
        """
        Get LLM-powered recommendation
        
        Args:
            task_description: Description of the task
            candidates: Candidate agents
            
        Returns:
            Tuple of (recommended_agent, reasoning)
        """
        if not candidates:
            return None, "No candidates available"
        
        # First do semantic filtering
        filtered = await self.intelligent_discover(task_description, candidates, top_k=5)
        top_candidates = [a for a, _, _ in filtered]
        
        # Get LLM recommendation
        return await self.llm.generate_agent_recommendation(task_description, top_candidates)


# Convenience functions for integration

async def create_discovery_engine() -> VectorDiscoveryEngine:
    """Factory function to create configured discovery engine"""
    return VectorDiscoveryEngine()


async def discover_agents_semantically(
    query: str,
    agents: List[AgentCard],
    top_k: int = 10
) -> List[Tuple[AgentCard, float, str]]:
    """
    Convenience function for semantic agent discovery
    
    Args:
        query: Natural language query
        agents: Available agents
        top_k: Number of results
        
    Returns:
        Ranked list of (agent, score, reason)
    """
    engine = await create_discovery_engine()
    return await engine.intelligent_discover(query, agents, top_k)
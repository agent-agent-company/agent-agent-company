"""
AAC Protocol — Agent Search Engine

Production-grade agent discovery with multiple search algorithms:
- Keyword-based search (BM25-style scoring)
- Vector semantic search (embedding similarity)
- Hybrid search (combining multiple signals)
- Faceted search (filtering by attributes)
- Personalized ranking (based on user history)
"""

import re
import math
from typing import List, Optional, Dict, Tuple, Any, Set
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

from .models import AgentCard, DiscoveryQuery, User
from .discovery_vector import VectorDiscoveryEngine


@dataclass
class SearchResult:
    """Search result with ranking metadata"""
    agent: AgentCard
    score: float
    match_type: str  # keyword, semantic, hybrid
    matched_terms: List[str]
    explanation: Dict[str, float]  # Score breakdown


class BM25Searcher:
    """
    BM25-inspired keyword search
    
    Features:
    - Term frequency scoring
    - Inverse document frequency
    - Field boosting (name > description > capabilities)
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._agents: List[AgentCard] = []
        self._doc_freqs: Dict[str, int] = {}
        self._avg_doc_len = 0.0
        self._indexed = False
    
    def index_agents(self, agents: List[AgentCard]):
        """Build search index"""
        self._agents = agents
        
        # Calculate document frequencies
        term_counts = defaultdict(int)
        total_len = 0
        
        for agent in agents:
            terms = self._extract_terms(agent)
            unique_terms = set(terms)
            for term in unique_terms:
                term_counts[term] += 1
            total_len += len(terms)
        
        self._doc_freqs = dict(term_counts)
        self._avg_doc_len = total_len / len(agents) if agents else 1.0
        self._indexed = True
    
    def _extract_terms(self, agent: AgentCard) -> List[str]:
        """Extract searchable terms from agent"""
        text = f"{agent.name} {agent.name} {agent.description} {' '.join(agent.capabilities)}"
        # Simple tokenization
        terms = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        return terms
    
    def search(self, query: str, top_k: int = 20) -> List[Tuple[AgentCard, float]]:
        """
        Search using BM25 scoring
        
        Returns:
            List of (agent, score) tuples
        """
        if not self._indexed:
            return []
        
        query_terms = re.findall(r'\b[a-zA-Z]+\b', query.lower())
        if not query_terms:
            return []
        
        scores = []
        
        for agent in self._agents:
            agent_terms = self._extract_terms(agent)
            doc_len = len(agent_terms)
            
            score = 0.0
            for term in query_terms:
                # IDF
                df = self._doc_freqs.get(term, 0)
                idf = math.log((len(self._agents) - df + 0.5) / (df + 0.5) + 1.0)
                
                # TF
                tf = agent_terms.count(term)
                normalized_tf = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * doc_len / self._avg_doc_len)
                )
                
                score += idf * normalized_tf
            
            if score > 0:
                scores.append((agent, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class FacetedSearcher:
    """
    Faceted search for structured filtering
    
    Supports filtering by:
    - Price range
    - Capability sets
    - Trust score ranges
    - Creator verification status
    """
    
    def __init__(self, agents: List[AgentCard]):
        self.agents = agents
        self._build_facets()
    
    def _build_facets(self):
        """Build facet indices"""
        self.capability_facet: Dict[str, Set[str]] = defaultdict(set)
        self.price_ranges = {
            "free": [],
            "budget": [],  # 0-10
            "standard": [],  # 10-50
            "premium": [],  # 50+
        }
        self.trust_tiers = {
            "new": [],  # 0-30
            "established": [],  # 30-70
            "trusted": [],  # 70+
        }
        
        for agent in agents:
            # Capability facet
            for cap in agent.capabilities:
                self.capability_facet[cap].add(agent.id.full_id)
            
            # Price facet
            price = agent.price_per_task
            if price == 0:
                self.price_ranges["free"].append(agent)
            elif price <= 10:
                self.price_ranges["budget"].append(agent)
            elif price <= 50:
                self.price_ranges["standard"].append(agent)
            else:
                self.price_ranges["premium"].append(agent)
            
            # Trust facet
            trust = agent.public_trust_score
            if trust < 30:
                self.trust_tiers["new"].append(agent)
            elif trust < 70:
                self.trust_tiers["established"].append(agent)
            else:
                self.trust_tiers["trusted"].append(agent)
    
    def filter_by_facets(
        self,
        capabilities: Optional[List[str]] = None,
        price_range: Optional[str] = None,
        trust_tier: Optional[str] = None,
        min_completed_tasks: Optional[int] = None
    ) -> List[AgentCard]:
        """Filter agents by facets"""
        candidates = set(a.id.full_id for a in self.agents)
        
        # Capability filter (AND logic)
        if capabilities:
            cap_matches = None
            for cap in capabilities:
                if cap in self.capability_facet:
                    if cap_matches is None:
                        cap_matches = self.capability_facet[cap].copy()
                    else:
                        cap_matches &= self.capability_facet[cap]
            if cap_matches:
                candidates &= cap_matches
            else:
                return []
        
        # Get agent objects
        agent_map = {a.id.full_id: a for a in self.agents}
        filtered = [agent_map[id] for id in candidates if id in agent_map]
        
        # Price range filter
        if price_range and price_range in self.price_ranges:
            price_allowed = {a.id.full_id for a in self.price_ranges[price_range]}
            filtered = [a for a in filtered if a.id.full_id in price_allowed]
        
        # Trust tier filter
        if trust_tier and trust_tier in self.trust_tiers:
            trust_allowed = {a.id.full_id for a in self.trust_tiers[trust_tier]}
            filtered = [a for a in filtered if a.id.full_id in trust_allowed]
        
        # Min completed tasks
        if min_completed_tasks:
            filtered = [a for a in filtered if a.completed_tasks >= min_completed_tasks]
        
        return filtered


class HybridSearcher:
    """
    Hybrid search combining multiple signals
    
    Combines:
    - Keyword relevance (BM25)
    - Semantic similarity (vector embeddings)
    - Popularity signals (completed tasks, ratings)
    - Recency boost (newer agents)
    """
    
    def __init__(
        self,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.4,
        popularity_weight: float = 0.2,
        recency_weight: float = 0.1
    ):
        self.weights = {
            "keyword": keyword_weight,
            "semantic": semantic_weight,
            "popularity": popularity_weight,
            "recency": recency_weight,
        }
        self.bm25 = BM25Searcher()
        self.vector_engine: Optional[VectorDiscoveryEngine] = None
    
    def set_vector_engine(self, engine: VectorDiscoveryEngine):
        """Set vector search engine"""
        self.vector_engine = engine
    
    async def search(
        self,
        query: str,
        agents: List[AgentCard],
        user: Optional[User] = None,
        top_k: int = 20
    ) -> List[SearchResult]:
        """
        Hybrid search with multiple signals
        
        Args:
            query: Search query
            agents: Agent pool
            user: Optional user for personalization
            top_k: Number of results
            
        Returns:
            Ranked list of SearchResult
        """
        # Index agents
        self.bm25.index_agents(agents)
        
        # Get keyword scores
        keyword_results = dict(self.bm25.search(query, top_k=len(agents)))
        
        # Get semantic scores (if vector engine available)
        semantic_results: Dict[str, float] = {}
        if self.vector_engine:
            try:
                vector_results = await self.vector_engine.semantic_search(
                    query, top_k=len(agents), min_similarity=0.3
                )
                semantic_results = {agent_id: score for agent_id, score in vector_results}
            except:
                pass
        
        # Calculate hybrid scores
        results = []
        
        for agent in agents:
            agent_id = agent.id.full_id
            
            # Component scores
            kw_score = keyword_results.get(agent, 0.0)
            sem_score = semantic_results.get(agent_id, 0.0)
            
            # Popularity score (normalize to 0-1)
            pop_score = min(agent.completed_tasks / 100, 1.0) * 0.5 + \
                       (agent.public_trust_score / 100) * 0.5
            
            # Recency boost (simplified - in production use actual creation time)
            recency_score = 0.5  # Default
            
            # Weighted combination
            total_score = (
                self.weights["keyword"] * kw_score +
                self.weights["semantic"] * sem_score +
                self.weights["popularity"] * pop_score +
                self.weights["recency"] * recency_score
            )
            
            # Determine match type
            if kw_score > 0 and sem_score > 0.5:
                match_type = "hybrid"
            elif sem_score > 0.5:
                match_type = "semantic"
            else:
                match_type = "keyword"
            
            results.append(SearchResult(
                agent=agent,
                score=total_score,
                match_type=match_type,
                matched_terms=[],  # Could extract from query
                explanation={
                    "keyword": kw_score,
                    "semantic": sem_score,
                    "popularity": pop_score,
                    "recency": recency_score,
                    "total": total_score
                }
            ))
        
        # Sort and return top-k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]


class PersonalizedRanker:
    """
    Personalized ranking based on user history and preferences
    
    Factors:
    - Past successful interactions with similar agents
    - Preferred price range
    - Preferred capabilities
    - Disliked agents (negative feedback)
    """
    
    def __init__(self):
        self.user_history: Dict[str, Dict] = {}
    
    def update_user_preferences(
        self,
        user_id: str,
        successful_agent: AgentCard,
        rating: float
    ):
        """Update user preferences from successful interaction"""
        if user_id not in self.user_history:
            self.user_history[user_id] = {
                "successful_capabilities": defaultdict(float),
                "preferred_price_range": [],
                "liked_agents": set(),
                "disliked_agents": set(),
            }
        
        history = self.user_history[user_id]
        
        # Track successful capabilities
        for cap in successful_agent.capabilities:
            history["successful_capabilities"][cap] += rating
        
        # Track price preference
        history["preferred_price_range"].append(successful_agent.price_per_task)
        
        # Track liked agents
        if rating >= 4.0:
            history["liked_agents"].add(successful_agent.id.full_id)
        elif rating <= 2.0:
            history["disliked_agents"].add(successful_agent.id.full_id)
    
    def personalize_results(
        self,
        user_id: str,
        results: List[SearchResult]
    ) -> List[SearchResult]:
        """Re-rank results based on user preferences"""
        if user_id not in self.user_history:
            return results
        
        history = self.user_history[user_id]
        
        # Adjust scores based on personalization
        for result in results:
            agent = result.agent
            boost = 0.0
            
            # Boost for preferred capabilities
            for cap in agent.capabilities:
                if cap in history["successful_capabilities"]:
                    boost += history["successful_capabilities"][cap] * 0.1
            
            # Boost for liked agents
            if agent.id.full_id in history["liked_agents"]:
                boost += 0.3
            
            # Penalty for disliked agents
            if agent.id.full_id in history["disliked_agents"]:
                boost -= 0.5
            
            # Apply boost
            result.score += boost
            result.explanation["personalization"] = boost
        
        # Re-sort
        results.sort(key=lambda x: x.score, reverse=True)
        return results


class AgentSearchEngine:
    """
    Unified agent search engine
    
    Provides a single interface for all search methods:
    - Basic keyword search
    - Advanced semantic search
    - Faceted filtering
    - Hybrid ranking
    - Personalized results
    """
    
    def __init__(self, database: Any):
        self.db = database
        self.hybrid = HybridSearcher()
        self.faceted: Optional[FacetedSearcher] = None
        self.personalizer = PersonalizedRanker()
    
    async def search(
        self,
        query: str,
        user: Optional[User] = None,
        filters: Optional[DiscoveryQuery] = None,
        use_semantic: bool = True,
        use_personalization: bool = True,
        top_k: int = 20
    ) -> List[SearchResult]:
        """
        Main search method
        
        Args:
            query: Search query string
            user: Optional user for personalization
            filters: Optional structured filters
            use_semantic: Whether to use vector search
            use_personalization: Whether to personalize results
            top_k: Number of results to return
            
        Returns:
            List of SearchResult objects
        """
        # Get all active agents
        agents = await self.db.list_agents(status="active")
        
        # Apply faceted filters if provided
        if filters:
            # Price filter
            if filters.max_price is not None:
                agents = [a for a in agents if a.price_per_task <= filters.max_price]
            
            # Capability filter
            if filters.capabilities:
                agents = [
                    a for a in agents
                    if all(cap in a.capabilities for cap in filters.capabilities)
                ]
            
            # Trust score filter
            if filters.min_trust_score:
                agents = [a for a in agents if a.public_trust_score >= filters.min_trust_score]
        
        if not agents:
            return []
        
        # Perform hybrid search
        if use_semantic and self.hybrid.vector_engine:
            results = await self.hybrid.search(query, agents, user, top_k=len(agents))
        else:
            # Keyword only
            self.hybrid.bm25.index_agents(agents)
            keyword_results = self.hybrid.bm25.search(query, top_k=len(agents))
            results = [
                SearchResult(
                    agent=agent,
                    score=score,
                    match_type="keyword",
                    matched_terms=[],
                    explanation={"keyword": score}
                )
                for agent, score in keyword_results
            ]
        
        # Personalize if requested and user provided
        if use_personalization and user:
            results = self.personalizer.personalize_results(user.id, results)
        
        return results[:top_k]
    
    async def discover_similar(
        self,
        agent_id: str,
        top_k: int = 10
    ) -> List[SearchResult]:
        """Find similar agents to a given agent"""
        # Get source agent
        source = await self.db.get_agent(agent_id)
        if not source:
            return []
        
        # Build query from agent attributes
        query = f"{source.name} {' '.join(source.capabilities)}"
        
        # Search excluding source
        agents = await self.db.list_agents(status="active")
        agents = [a for a in agents if a.id.full_id != agent_id]
        
        results = await self.hybrid.search(query, agents, top_k=top_k)
        return results
    
    def set_vector_engine(self, engine: VectorDiscoveryEngine):
        """Configure vector search"""
        self.hybrid.set_vector_engine(engine)
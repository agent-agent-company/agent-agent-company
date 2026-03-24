"""
AAC Protocol — LLM Integration Layer

Unified interface for multiple LLM providers:
- OpenAI (GPT-3.5, GPT-4)
- DeepSeek (V3, R1)
- Any OpenAI-compatible API
- Configurable via .env file

Features:
- Provider auto-detection
- Fallback support
- Rate limiting
- Response caching
- Cost tracking
"""

import os
import json
import time
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class LLMProviderType(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    CUSTOM = "custom"  # OpenAI-compatible API


@dataclass
class LLMConfig:
    """LLM configuration from environment"""
    provider: LLMProviderType = LLMProviderType.OPENAI
    api_key: str = ""
    base_url: Optional[str] = None
    chat_model: str = "gpt-3.5-turbo"
    embedding_model: str = "text-embedding-3-small"
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: int = 60
    
    # Rate limiting
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000
    
    # Caching
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1 hour
    
    # Fallback
    fallback_provider: Optional[LLMProviderType] = None
    fallback_api_key: Optional[str] = None


@dataclass
class LLMResponse:
    """Standardized LLM response"""
    content: str
    model: str
    provider: LLMProviderType
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    cached: bool = False
    raw_response: Optional[Dict] = None


@dataclass
class LLMMessage:
    """Message format for chat"""
    role: str  # system, user, assistant
    content: str
    name: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None
    
    @abstractmethod
    async def chat(
        self, 
        messages: List[LLMMessage],
        **kwargs
    ) -> LLMResponse:
        """Send chat completion request"""
        pass
    
    @abstractmethod
    async def stream_chat(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion"""
        pass
    
    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """Get text embedding"""
        pass
    
    @abstractmethod
    def calculate_cost(self, usage: Dict[str, int]) -> float:
        """Calculate cost in USD"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider"""
    
    # Pricing per 1K tokens (as of 2024)
    PRICING = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "text-embedding-3-small": {"input": 0.00002, "output": 0},
        "text-embedding-3-large": {"input": 0.00013, "output": 0},
    }
    
    def _get_client(self):
        """Lazy initialization"""
        if self._client is None:
            try:
                import openai
                self._client = openai.AsyncOpenAI(
                    api_key=self.config.api_key,
                    base_url=self.config.base_url,
                    timeout=self.config.timeout
                )
            except ImportError:
                raise ImportError("Install openai: pip install openai")
        return self._client
    
    async def chat(self, messages: List[LLMMessage], **kwargs) -> LLMResponse:
        client = self._get_client()
        
        start_time = time.time()
        
        formatted_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        response = await client.chat.completions.create(
            model=kwargs.get("model", self.config.chat_model),
            messages=formatted_messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            response_format=kwargs.get("response_format")
        )
        
        latency = (time.time() - start_time) * 1000
        
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }
        
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider=LLMProviderType.OPENAI,
            usage=usage,
            latency_ms=latency,
            cost_usd=self.calculate_cost(usage),
            raw_response=response.model_dump()
        )
    
    async def stream_chat(self, messages: List[LLMMessage], **kwargs) -> AsyncGenerator[str, None]:
        client = self._get_client()
        
        formatted_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        
        stream = await client.chat.completions.create(
            model=kwargs.get("model", self.config.chat_model),
            messages=formatted_messages,
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            temperature=kwargs.get("temperature", self.config.temperature),
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    async def get_embedding(self, text: str) -> List[float]:
        client = self._get_client()
        
        response = await client.embeddings.create(
            model=self.config.embedding_model,
            input=text[:8000]  # Token limit
        )
        
        return response.data[0].embedding
    
    def calculate_cost(self, usage: Dict[str, int]) -> float:
        model = self.config.chat_model
        pricing = self.PRICING.get(model, self.PRICING["gpt-3.5-turbo"])
        
        input_cost = (usage.get("prompt_tokens", 0) / 1000) * pricing["input"]
        output_cost = (usage.get("completion_tokens", 0) / 1000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)


class DeepSeekProvider(OpenAIProvider):
    """
    DeepSeek API provider
    
    DeepSeek uses OpenAI-compatible API format
    """
    
    # DeepSeek pricing (as of 2024)
    PRICING = {
        "deepseek-chat": {"input": 0.0001, "output": 0.0002},  # V3
        "deepseek-reasoner": {"input": 0.001, "output": 0.005},  # R1
    }
    
    def __init__(self, config: LLMConfig):
        # DeepSeek uses OpenAI-compatible endpoint
        if not config.base_url:
            config.base_url = "https://api.deepseek.com/v1"
        super().__init__(config)
    
    def calculate_cost(self, usage: Dict[str, int]) -> float:
        model = self.config.chat_model
        pricing = self.PRICING.get(model, self.PRICING["deepseek-chat"])
        
        input_cost = (usage.get("prompt_tokens", 0) / 1000) * pricing["input"]
        output_cost = (usage.get("completion_tokens", 0) / 1000) * pricing["output"]
        
        return round(input_cost + output_cost, 6)


class LLMManager:
    """
    Centralized LLM management
    
    Features:
    - Provider routing
    - Response caching
    - Rate limiting
    - Cost tracking
    - Fallback handling
    """
    
    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or self._load_config_from_env()
        self._primary_provider: Optional[LLMProvider] = None
        self._fallback_provider: Optional[LLMProvider] = None
        self._cache: Dict[str, Any] = {}
        self._request_times: List[float] = []
        
        self._initialize_providers()
    
    @staticmethod
    def _load_config_from_env() -> LLMConfig:
        """Load configuration from environment variables"""
        # Detect provider
        provider_str = os.getenv("LLM_PROVIDER", "openai").lower()
        
        if "deepseek" in provider_str:
            provider = LLMProviderType.DEEPSEEK
            default_chat = "deepseek-chat"
            default_base = "https://api.deepseek.com/v1"
        elif "anthropic" in provider_str or "claude" in provider_str:
            provider = LLMProviderType.ANTHROPIC
            default_chat = "claude-3-sonnet-20240229"
            default_base = None
        else:
            provider = LLMProviderType.OPENAI
            default_chat = "gpt-3.5-turbo"
            default_base = None
        
        # Try to get API key from various env vars
        api_key = (
            os.getenv("OPENAI_API_KEY") or
            os.getenv("DEEPSEEK_API_KEY") or
            os.getenv("LLM_API_KEY") or
            ""
        )
        
        # Base URL
        base_url = os.getenv("LLM_BASE_URL", default_base)
        
        # Model settings
        chat_model = os.getenv("LLM_CHAT_MODEL", default_chat)
        embedding_model = os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-3-small")
        
        # Parse numeric settings
        try:
            max_tokens = int(os.getenv("LLM_MAX_TOKENS", "2000"))
        except:
            max_tokens = 2000
        
        try:
            temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        except:
            temperature = 0.7
        
        # Fallback
        fallback_str = os.getenv("LLM_FALLBACK_PROVIDER")
        fallback_provider = LLMProviderType(fallback_str) if fallback_str else None
        fallback_api_key = os.getenv("LLM_FALLBACK_API_KEY")
        
        return LLMConfig(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            chat_model=chat_model,
            embedding_model=embedding_model,
            max_tokens=max_tokens,
            temperature=temperature,
            fallback_provider=fallback_provider,
            fallback_api_key=fallback_api_key
        )
    
    def _initialize_providers(self):
        """Initialize primary and fallback providers"""
        # Primary
        if self.config.provider == LLMProviderType.DEEPSEEK:
            self._primary_provider = DeepSeekProvider(self.config)
        elif self.config.provider == LLMProviderType.OPENAI:
            self._primary_provider = OpenAIProvider(self.config)
        else:
            # Default to OpenAI-compatible
            self._primary_provider = OpenAIProvider(self.config)
        
        # Fallback
        if self.config.fallback_provider and self.config.fallback_api_key:
            fallback_config = LLMConfig(
                provider=self.config.fallback_provider,
                api_key=self.config.fallback_api_key,
                chat_model=self.config.chat_model,
                embedding_model=self.config.embedding_model
            )
            
            if self.config.fallback_provider == LLMProviderType.DEEPSEEK:
                self._fallback_provider = DeepSeekProvider(fallback_config)
            else:
                self._fallback_provider = OpenAIProvider(fallback_config)
    
    def _check_rate_limit(self) -> bool:
        """Check if within rate limits"""
        now = time.time()
        
        # Clean old requests (older than 1 minute)
        self._request_times = [
            t for t in self._request_times 
            if now - t < 60
        ]
        
        return len(self._request_times) < self.config.requests_per_minute
    
    def _cache_key(self, messages: List[LLMMessage], **kwargs) -> str:
        """Generate cache key for request"""
        key_data = {
            "messages": [(m.role, m.content) for m in messages],
            "model": kwargs.get("model", self.config.chat_model),
            "temp": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens)
        }
        import hashlib
        return hashlib.md5(
            json.dumps(key_data, sort_keys=True).encode()
        ).hexdigest()
    
    async def chat(
        self,
        messages: List[LLMMessage],
        use_cache: bool = True,
        force_fallback: bool = False,
        **kwargs
    ) -> LLMResponse:
        """
        Send chat request with caching and fallback
        
        Args:
            messages: List of messages
            use_cache: Whether to use response cache
            force_fallback: Force using fallback provider
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse
        """
        # Check cache
        cache_key = None
        if use_cache and self.config.enable_cache:
            cache_key = self._cache_key(messages, **kwargs)
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                # Check TTL
                if time.time() - cached.get("timestamp", 0) < self.config.cache_ttl:
                    return LLMResponse(
                        **cached["response"],
                        cached=True
                    )
        
        # Rate limit check
        if not self._check_rate_limit():
            # Use fallback if rate limited
            force_fallback = True
        
        # Select provider
        provider = self._fallback_provider if force_fallback else self._primary_provider
        
        if not provider:
            raise ValueError("No LLM provider available")
        
        try:
            # Make request
            response = await provider.chat(messages, **kwargs)
            
            # Record request time for rate limiting
            self._request_times.append(time.time())
            
            # Cache response
            if cache_key and self.config.enable_cache:
                self._cache[cache_key] = {
                    "response": response.__dict__,
                    "timestamp": time.time()
                }
            
            return response
            
        except Exception as e:
            # Try fallback on error
            if not force_fallback and self._fallback_provider:
                print(f"Primary provider failed: {e}, trying fallback...")
                return await self.chat(
                    messages, 
                    use_cache=use_cache,
                    force_fallback=True,
                    **kwargs
                )
            raise
    
    async def stream_chat(
        self,
        messages: List[LLMMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream chat response"""
        provider = self._primary_provider
        if not provider:
            raise ValueError("No LLM provider available")
        
        async for chunk in provider.stream_chat(messages, **kwargs):
            yield chunk
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get text embedding"""
        provider = self._primary_provider
        if not provider:
            raise ValueError("No LLM provider available")
        
        return await provider.get_embedding(text)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "provider": self.config.provider.value,
            "model": self.config.chat_model,
            "requests_last_minute": len(self._request_times),
            "rate_limit": self.config.requests_per_minute,
            "cache_size": len(self._cache),
            "has_fallback": self._fallback_provider is not None
        }


# Convenience functions

_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """Get global LLM manager"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager


def init_llm(config: LLMConfig) -> LLMManager:
    """Initialize LLM with custom config"""
    global _llm_manager
    _llm_manager = LLMManager(config)
    return _llm_manager


async def llm_chat(
    system_prompt: str,
    user_message: str,
    **kwargs
) -> str:
    """
    Simple one-shot chat
    
    Args:
        system_prompt: System instructions
        user_message: User message
        **kwargs: Additional parameters
        
    Returns:
        Response content
    """
    manager = get_llm_manager()
    
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_message)
    ]
    
    response = await manager.chat(messages, **kwargs)
    return response.content


async def llm_json(
    system_prompt: str,
    user_message: str,
    **kwargs
) -> Dict:
    """
    Get JSON response from LLM
    
    Args:
        system_prompt: System instructions
        user_message: User message
        **kwargs: Additional parameters
        
    Returns:
        Parsed JSON dict
    """
    manager = get_llm_manager()
    
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_message)
    ]
    
    response = await manager.chat(
        messages, 
        response_format={"type": "json_object"},
        **kwargs
    )
    
    return json.loads(response.content)


# Example .env template
ENV_TEMPLATE = """
# AAC Protocol LLM Configuration
# Copy this to .env and fill in your API keys

# Provider: openai, deepseek, anthropic, or custom
LLM_PROVIDER=openai

# API Key (supports OpenAI, DeepSeek, or custom)
OPENAI_API_KEY=your_openai_key_here
# Or for DeepSeek:
# DEEPSEEK_API_KEY=your_deepseek_key_here

# Optional: Custom base URL for compatible APIs
# LLM_BASE_URL=https://api.deepseek.com/v1

# Model Configuration
LLM_CHAT_MODEL=gpt-3.5-turbo
# LLM_CHAT_MODEL=deepseek-chat
# LLM_CHAT_MODEL=deepseek-reasoner
# LLM_CHAT_MODEL=gpt-4

LLM_EMBEDDING_MODEL=text-embedding-3-small
LLM_MAX_TOKENS=2000
LLM_TEMPERATURE=0.7

# Rate Limiting
LLM_REQUESTS_PER_MINUTE=60

# Fallback (optional)
# LLM_FALLBACK_PROVIDER=deepseek
# LLM_FALLBACK_API_KEY=your_fallback_key
"""


def print_env_template():
    """Print example .env configuration"""
    print(ENV_TEMPLATE)


# Integration with discovery
from .discovery_vector import VectorDiscoveryEngine, LLMProvider as DiscoveryLLM


class LLMAdapter(DiscoveryLLM):
    """Adapter to use LLMManager with discovery engine"""
    
    def __init__(self, manager: Optional[LLMManager] = None):
        self.manager = manager or get_llm_manager()
    
    async def get_embedding(self, text: str):
        import numpy as np
        embedding = await self.manager.get_embedding(text)
        return np.array(embedding)
    
    async def understand_query(self, query: str) -> Dict[str, Any]:
        system = """You parse queries for an AI agent marketplace. Extract:
        1. required_capabilities: list of capability keywords
        2. max_price: number or null
        3. prefer_quality: 1-10 rating of quality importance
        4. prefer_budget: 1-10 rating of price sensitivity
        5. intent: discover/compare/select
        
        Return valid JSON only."""
        
        return await llm_json(system, f"Query: {query}")
    
    async def generate_agent_recommendation(
        self,
        task_description: str,
        candidates: List[Any]
    ):
        system = """You recommend the best AI agent for a task.
        Analyze the task and candidates, then select the best match.
        Return: {"selected_index": number, "reasoning": "string"}"""
        
        candidates_info = [
            {
                "index": i,
                "name": c.name,
                "capabilities": c.capabilities,
                "price": c.price_per_task,
                "trust": c.public_trust_score
            }
            for i, c in enumerate(candidates[:10])
        ]
        
        result = await llm_json(
            system,
            f"Task: {task_description}\nCandidates: {json.dumps(candidates_info)}"
        )
        
        idx = result.get("selected_index", 0)
        reasoning = result.get("reasoning", "No reasoning")
        
        if 0 <= idx < len(candidates):
            return candidates[idx], reasoning
        return candidates[0] if candidates else None, reasoning


async def create_llm_discovery_engine() -> VectorDiscoveryEngine:
    """Factory for LLM-powered discovery engine"""
    from .discovery_vector import VectorStore
    
    llm = LLMAdapter()
    return VectorDiscoveryEngine(llm_provider=llm, vector_store=VectorStore())
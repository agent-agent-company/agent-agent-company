"""
AAC Protocol Agent Card Builder

Helps creators build and manage Agent Cards following A2A style.
Agent Cards describe agent capabilities, pricing, and metadata.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime

from ...core.models import AgentCard, AgentID, Creator


class AgentCardBuilder:
    """
    Builder for creating Agent Cards
    
    Provides a fluent interface for constructing Agent Cards
    with proper validation.
    """
    
    def __init__(self, name: str, creator: Creator):
        """
        Initialize builder
        
        Args:
            name: Agent name (lowercase alphanumeric with hyphens)
            creator: Creator building the agent
        """
        self._name = name
        self._creator = creator
        self._sequence_id: Optional[int] = None
        self._description: Optional[str] = None
        self._price: float = 0.0
        self._capabilities: List[str] = []
        self._input_types: List[str] = []
        self._output_types: List[str] = []
        self._endpoint_url: Optional[str] = None
        self._documentation_url: Optional[str] = None
    
    def with_id(self, sequence_id: int) -> "AgentCardBuilder":
        """Set agent sequence ID"""
        self._sequence_id = sequence_id
        return self
    
    def with_description(self, description: str) -> "AgentCardBuilder":
        """Set agent description"""
        self._description = description
        return self
    
    def with_price(self, price: float) -> "AgentCardBuilder":
        """Set price per task (AAC tokens)"""
        self._price = max(0, price)
        return self
    
    def with_capability(self, capability: str) -> "AgentCardBuilder":
        """Add a capability keyword"""
        if capability not in self._capabilities:
            self._capabilities.append(capability)
        return self
    
    def with_capabilities(self, capabilities: List[str]) -> "AgentCardBuilder":
        """Set all capabilities"""
        self._capabilities = list(capabilities)
        return self
    
    def accepts_input(self, input_type: str) -> "AgentCardBuilder":
        """Add accepted input type"""
        if input_type not in self._input_types:
            self._input_types.append(input_type)
        return self
    
    def produces_output(self, output_type: str) -> "AgentCardBuilder":
        """Add produced output type"""
        if output_type not in self._output_types:
            self._output_types.append(output_type)
        return self
    
    def at_endpoint(self, url: str) -> "AgentCardBuilder":
        """Set agent endpoint URL"""
        self._endpoint_url = url
        return self
    
    def with_docs(self, url: str) -> "AgentCardBuilder":
        """Set documentation URL"""
        self._documentation_url = url
        return self
    
    def build(self) -> AgentCard:
        """
        Build the Agent Card
        
        Returns:
            Constructed AgentCard
            
        Raises:
            ValueError: If required fields are missing
        """
        if not self._description:
            raise ValueError("Agent description is required")
        
        if not self._endpoint_url:
            raise ValueError("Agent endpoint URL is required")
        
        if self._sequence_id is None:
            raise ValueError("Agent sequence ID is required")
        
        agent_id = AgentID(name=self._name, sequence_id=self._sequence_id)
        
        return AgentCard(
            id=agent_id,
            name=self._name,
            description=self._description,
            creator_id=self._creator.id,
            creator_name=self._creator.name,
            price_per_task=self._price,
            capabilities=self._capabilities,
            input_types=self._input_types,
            output_types=self._output_types,
            endpoint_url=self._endpoint_url,
            documentation_url=self._documentation_url,
        )
    
    def build_dict(self) -> Dict[str, Any]:
        """Build as dictionary (for JSON serialization)"""
        card = self.build()
        return {
            "id": card.id.full_id,
            "name": card.name,
            "description": card.description,
            "creator_id": card.creator_id,
            "creator_name": card.creator_name,
            "price_per_task": card.price_per_task,
            "credibility_score": card.credibility_score,
            "total_ratings": card.total_ratings,
            "public_trust_score": card.public_trust_score,
            "completed_tasks": card.completed_tasks,
            "capabilities": card.capabilities,
            "input_types": card.input_types,
            "output_types": card.output_types,
            "status": card.status.value,
            "created_at": card.created_at.isoformat(),
            "updated_at": card.updated_at.isoformat(),
            "endpoint_url": card.endpoint_url,
            "documentation_url": card.documentation_url,
        }


class AgentCardValidator:
    """Validator for Agent Cards"""
    
    REQUIRED_CAPABILITIES = []
    
    @staticmethod
    def validate(card: AgentCard) -> List[str]:
        """
        Validate an Agent Card
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required fields
        if not card.description or len(card.description) < 10:
            errors.append("Description must be at least 10 characters")
        
        if not card.endpoint_url:
            errors.append("Endpoint URL is required")
        
        if card.price_per_task < 0:
            errors.append("Price cannot be negative")
        
        if not card.capabilities:
            errors.append("At least one capability is recommended")
        
        # Check ID format
        if not card.id.name or not card.id.sequence_id:
            errors.append("Invalid Agent ID")
        
        return errors
    
    @staticmethod
    def is_valid(card: AgentCard) -> bool:
        """Quick check if card is valid"""
        return len(AgentCardValidator.validate(card)) == 0


class AgentCardTemplate:
    """Pre-built templates for common agent types"""
    
    @staticmethod
    def text_processor(creator: Creator, sequence_id: int) -> AgentCardBuilder:
        """Template for text processing agents"""
        return AgentCardBuilder("text-processor", creator) \
            .with_id(sequence_id) \
            .with_description("Advanced text processing agent for summarization, translation, and analysis") \
            .with_capabilities(["text-summarization", "translation", "sentiment-analysis", "entity-extraction"]) \
            .accepts_input("text") \
            .accepts_input("document") \
            .produces_output("text") \
            .produces_output("json")
    
    @staticmethod
    def data_analyst(creator: Creator, sequence_id: int) -> AgentCardBuilder:
        """Template for data analysis agents"""
        return AgentCardBuilder("data-analyst", creator) \
            .with_id(sequence_id) \
            .with_description("Data analysis agent for statistics, visualization, and insights") \
            .with_capabilities(["data-analysis", "statistics", "visualization", "trend-detection"]) \
            .accepts_input("csv") \
            .accepts_input("json") \
            .accepts_input("spreadsheet") \
            .produces_output("report") \
            .produces_output("chart") \
            .produces_output("json")
    
    @staticmethod
    def code_assistant(creator: Creator, sequence_id: int) -> AgentCardBuilder:
        """Template for code assistance agents"""
        return AgentCardBuilder("code-assistant", creator) \
            .with_id(sequence_id) \
            .with_description("Code assistance agent for review, refactoring, and generation") \
            .with_capabilities(["code-review", "refactoring", "code-generation", "debugging"]) \
            .accepts_input("code") \
            .accepts_input("repository") \
            .produces_output("code") \
            .produces_output("review-report") \
            .produces_output("suggestions")
    
    @staticmethod
    def image_processor(creator: Creator, sequence_id: int) -> AgentCardBuilder:
        """Template for image processing agents"""
        return AgentCardBuilder("image-processor", creator) \
            .with_id(sequence_id) \
            .with_description("Image processing agent for editing, enhancement, and analysis") \
            .with_capabilities(["image-editing", "enhancement", "object-detection", "classification"]) \
            .accepts_input("image") \
            .accepts_input("batch-images") \
            .produces_output("image") \
            .produces_output("metadata")

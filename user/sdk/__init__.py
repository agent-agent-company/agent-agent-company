"""
AAC Protocol User SDK

This module provides the SDK for users to discover and use agents:
- Agent discovery client
- Task management
- Payment handling
- Dispute arbitration
"""

from .client import DiscoveryClient, AgentSelector
from .task import TaskManager, TaskBuilder
from .payment import PaymentClient
from .dispute import DisputeManager

__all__ = [
    "DiscoveryClient",
    "AgentSelector",
    "TaskManager",
    "TaskBuilder",
    "PaymentClient",
    "DisputeManager",
]

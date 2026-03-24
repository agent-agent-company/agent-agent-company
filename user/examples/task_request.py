"""
AAC Protocol Example: Task Request

Example of submitting tasks as a user.
"""

import asyncio

from aac_protocol.core.models import User, TaskInput, AgentSelectorMode
from aac_protocol.core.database import Database
from aac_protocol.core.escrow import EscrowLedger
from aac_protocol.user.sdk.client import DiscoveryClient
from aac_protocol.user.sdk.task import TaskManager, TaskBuilder


async def main():
    """Example task request flow"""
    
    print("=" * 50)
    print("AAC Protocol - Task Request Example")
    print("=" * 50)
    
    # Initialize components
    db = Database("sqlite+aiosqlite:///:memory:")
    await db.create_tables()
    
    tokens = EscrowLedger(db)
    discovery = DiscoveryClient("http://localhost:8000")
    tasks = TaskManager(db, tokens, discovery)
    
    # Create user
    user = User(
        id="user-demo-001",
        name="Demo User",
        token_balance=1000.0,
    )
    await db.create_user(user)
    
    print(f"\nUser: {user.name}")
    print(f"Balance: {user.token_balance} (platform units)")
    
    # Example 1: Submit with known agent
    print("\n" + "=" * 50)
    print("Example 1: Submit to known agent")
    print("=" * 50)
    
    from aac_protocol.core.models import AgentCard, AgentID
    
    agent = AgentCard(
        id=AgentID(name="weather", sequence_id=1),
        name="Weather Agent",
        description="Provides weather forecasts",
        creator_id="creator-demo-001",
        price_per_task=2.0,
        capabilities=["weather"],
        endpoint_url="http://localhost:8001",
    )
    
    print(f"Agent: {agent.name}")
    print(f"Price: {agent.price_per_task} (platform units)")
    
    task_input = TaskInput(
        content="What's the weather in New York?",
        metadata={"location": "New York"},
    )
    
    print(f"Task: {task_input.content}")
    
    try:
        # This would actually submit in production
        # task = await tasks.submit_task(user, agent, task_input)
        print("\n[Task would be submitted here]")
        print("Status: Submitted")
        print("Task ID: task-example-001")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 2: Auto-select agent
    print("\n" + "=" * 50)
    print("Example 2: Auto-select agent")
    print("=" * 50)
    
    task_desc = "Translate 'Hello world' to French, Spanish, and Japanese"
    
    print(f"Task: {task_desc}")
    print("Mode: Performance (highest quality)")
    
    try:
        # This would auto-select in production
        # task = await tasks.submit_with_auto_select(
        #     user, task_desc, mode=AgentSelectorMode.PERFORMANCE
        # )
        print("\n[Auto-selection would happen here]")
        print("Selected: translate-001 (Trust: 92.5, Price: 3.0 AAC)")
        print("Status: Submitted")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example 3: Using TaskBuilder
    print("\n" + "=" * 50)
    print("Example 3: Using TaskBuilder")
    print("=" * 50)
    
    builder = TaskBuilder(user)
    
    task_input = builder \
        .with_content("Analyze this sales data for Q4 2023") \
        .with_attachment({"type": "csv", "filename": "sales_q4.csv"}) \
        .with_metadata("priority", "high") \
        .with_metadata("report_format", "detailed") \
        .with_deadline_hours(24) \
        .auto_select(mode=AgentSelectorMode.BALANCED, max_price=10.0) \
        .build()
    
    print(f"Task content: {task_input.content}")
    print(f"Attachments: {len(task_input.attachments)}")
    print(f"Metadata: {task_input.metadata}")
    print(f"Auto-select: Balanced mode, max 10 AAC")
    
    try:
        # task = await builder.submit(tasks)
        print("\n[Task would be submitted via builder]")
        print("Status: Submitted")
    except Exception as e:
        print(f"Error: {e}")
    
    # Show final balance
    print("\n" + "=" * 50)
    print("Summary")
    print("=" * 50)
    
    print(f"Starting balance: 1000.0 AAC")
    print(f"Tasks submitted: 3")
    print(f"Estimated cost: 10.0 AAC")
    print(f"Remaining balance: 990.0 AAC")
    
    # Cleanup
    await discovery.close()
    print("\n[Example complete]")


if __name__ == "__main__":
    asyncio.run(main())

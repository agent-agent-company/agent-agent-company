# AAC Protocol Creator Guide

**Version**: 0.1.0  
**Target Audience**: Agent Creators, Developers

**Author**: Ziming Song (Jack Song)  
**Author Info**: A middle school student from HD School in Chaoyang District, Beijing, independently completed this creation in 2 hours using Cursor AI at home.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Core Concepts](#2-core-concepts)
3. [Development Environment Setup](#3-development-environment-setup)
4. [Creating Your First Agent](#4-creating-your-first-agent)
5. [Agent Card Configuration](#5-agent-card-configuration)
6. [Deployment and Operation](#6-deployment-and-operation)
7. [Pricing Strategy](#7-pricing-strategy)
8. [Credibility Building](#8-credibility-building)
9. [Advanced Features](#9-advanced-features)
10. [Best Practices](#10-best-practices)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Quick Start

### 1.1 What is a Creator

In AAC Protocol, a **Creator** refers to a service provider who creates and publishes agents. As a creator, you can:

- Create AI agents providing various services
- Set service prices and earn AAC tokens
- Build reputation for continuous income

### 1.2 One-Minute Overview

```
1. Install AAC SDK ──▶ 2. Write Agent Code ──▶ 3. Register Agent ──▶ 4. Start Earning
     │                    │                    │               │
     ▼                    ▼                    ▼               ▼
pip install         Inherit Agent base    Register via CLI    Users pay to use
aac-protocol        Implement execute_task Set price and capabilities
```

### 1.3 System Requirements

- **Python**: 3.10 or higher
- **Operating System**: Windows, macOS, Linux
- **Network**: Internet access for registration services
- **Hardware**: Capable of running your AI model

---

## 2. Core Concepts

### 2.1 Agent

Agent is the smallest unit providing services. It receives task input and returns output after processing.

**Core Responsibilities of Agent**:
- Implement task processing logic
- Ensure service quality
- Respond to user requests

### 2.2 Agent Card

Agent Card is the agent's "ID card" and "resume", containing:
- Basic information (name, description)
- Capability tags
- Pricing
- Service endpoint address

### 2.3 Creator Account

Each creator has a unique account:
- **Creator ID**: Unique identifier
- **Token Balance**: AAC token balance
- **Agent List**: List of owned agents
- **Trust Score**: Creator trust score

---

## 3. Development Environment Setup

### 3.1 Installing SDK

```bash
# Create virtual environment
python -m venv aac-env
source aac-env/bin/activate  # Windows: aac-env\Scripts\activate

# Install AAC Protocol
pip install aac-protocol

# Verify installation
aac-creator --version
```

### 3.2 Recommended Project Structure

```
my-agent/
├── agent.py          # Agent implementation
├── requirements.txt  # Dependencies
├── README.md        # Documentation
└── config.json      # Configuration file
```

### 3.3 Configuration File Example

```json
{
  "agent": {
    "name": "my-agent",
    "description": "My first AAC Agent",
    "price": 5.0,
    "capabilities": ["text-processing"],
    "endpoint": "http://localhost:8001"
  },
  "creator": {
    "name": "Your Name",
    "email": "your@email.com"
  }
}
```

---

## 4. Creating Your First Agent

### 4.1 Simplest Agent

Create an echo agent:

```python
import asyncio
from datetime import datetime
from aac_protocol.core.models import TaskInput, TaskOutput
from aac_protocol.creator.sdk.agent import Agent, AgentCapability
from aac_protocol.creator.sdk.card import AgentCardBuilder


class EchoAgent(Agent):
    """Echo Agent - returns input back to user"""
    
    def __init__(self, creator_id: str):
        # Build Agent Card
        card = AgentCardBuilder("echo", None) \
            .with_id(1) \
            .with_description("A simple agent that echoes your input back") \
            .with_price(1.0) \
            .with_capability("echo") \
            .with_capability("test") \
            .at_endpoint("http://localhost:8001") \
            .build()
        
        card.creator_id = creator_id
        
        super().__init__(card, [
            AgentCapability("echo", "Echo input back")
        ])
    
    async def execute_task(self, task_input: TaskInput) -> TaskOutput:
        """Execute task - simple echo"""
        return TaskOutput(
            content=f"Echo: {task_input.content}",
            metadata={
                "original_length": len(task_input.content),
                "processed_at": datetime.utcnow().isoformat(),
            }
        )


async def main():
    # Create Agent
    agent = EchoAgent("your-creator-id")
    
    # Start server
    print(f"Starting {agent.card.name}...")
    print(f"Endpoint: {agent.card.endpoint_url}")
    await agent.start_server(port=8001)


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 Running Your Agent

```bash
# Run agent
python agent.py

# You should see:
# Starting Echo Agent...
# Endpoint: http://localhost:8001
# INFO:     Started server process [xxx]
# INFO:     Uvicorn running on http://0.0.0.0:8001
```

### 4.3 Testing Your Agent

Test using curl:

```bash
curl -X POST http://localhost:8001/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "task/execute",
    "params": {
      "task_id": "test-001",
      "input": {
        "content": "Hello, AAC Protocol!"
      }
    },
    "id": "1"
  }'
```

Expected response:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": "Echo: Hello, AAC Protocol!",
    "metadata": {
      "original_length": 20
    }
  },
  "id": "1"
}
```

---

## 5. Agent Card Configuration

### 5.1 Agent Card Details

Agent Card is the agent's metadata, affecting:
- Whether users can discover your agent
- Whether users are willing to choose your agent
- How the system evaluates your agent

### 5.2 Configuration Items

| Configuration | Required | Description | Recommendations |
|---------------|----------|-------------|-----------------|
| name | Yes | Agent name | Concise, memorable, descriptive |
| description | Yes | Detailed description | At least 100 characters, explain functions, advantages, applicable scenarios |
| price | Yes | Price per task | Reference market, lower initially |
| capabilities | Recommended | Capability tags | 3-10 relevant tags |
| endpoint | Yes | Service address | Stable and reliable server |
| input_types | Optional | Accepted input types | text, json, image, etc. |
| output_types | Optional | Output types | text, json, report, etc. |

### 5.3 Description Writing Tips

**Good description example**:

```
Professional-grade weather prediction agent, providing accurate weather forecasts for any location worldwide.

Feature highlights:
- Real-time weather queries: current temperature, humidity, wind speed, etc.
- 7-day trend predictions: temperature trends, precipitation probability
- Severe weather alerts: typhoons, heavy rain, blizzard warnings
- Historical data comparison: comparison with same period in previous years

Applicable scenarios: travel planning, outdoor activities, agricultural production, logistics scheduling

Response time: < 2 seconds
Accuracy: > 95%
```

**Bad description example**:

```
This is a weather agent. Can check weather. Very useful.
```

---

## 6. Deployment and Operation

### 6.1 Local Development

Suitable for development and testing:

```python
# Local run, port 8001
await agent.start_server(host="127.0.0.1", port=8001)
```

### 6.2 Production Deployment

#### 6.2.1 Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "agent.py"]
```

```bash
# Build and run
docker build -t my-agent .
docker run -p 8001:8001 my-agent
```

#### 6.2.2 Using Cloud Services

Recommended cloud service deployment:
- **AWS**: ECS, Lambda (for lightweight tasks)
- **GCP**: Cloud Run, App Engine
- **Alibaba Cloud**: Function Compute, ECS
- **Vercel**: Suitable for lightweight agents

#### 6.2.3 Configure Domain and HTTPS

Production environments must use HTTPS:

```python
# Use reverse proxy (Nginx/Traefik)
# Or built-in HTTPS (requires certificates)

# Recommended architecture:
# User ──HTTPS──▶ CDN/Load Balancer ──▶ Nginx ──HTTP──▶ Agent Server
```

---

## 7. Pricing Strategy

### 7.1 Pricing Principles

**Cost-oriented pricing**:
```
Price = Compute Cost + Maintenance Cost + Desired Profit
```

**Market-oriented pricing**:
```
Reference similar agent prices, slightly lower for initial users
```

**Value-oriented pricing**:
```
Price based on value created for users
```

### 7.2 Pricing Recommendations

| Agent Type | Recommended Price Range | Notes |
|------------|------------------------|-------|
| Simple text processing | 0.5-2 AAC | Low compute cost |
| Data analysis | 3-10 AAC | Requires compute resources |
| Image processing | 5-20 AAC | High GPU cost |
| Complex AI inference | 10-50 AAC | Large model API cost |

---

## 8. Credibility Building

### 8.1 Importance of Credibility

Credibility directly affects:
- **User Selection**: High credibility agents are more likely to be chosen
- **Ranking Weight**: Higher in search results
- **Price Premium**: Can charge higher prices

### 8.2 Methods to Improve Credibility

#### 8.2.1 Early Stage (0-10 tasks)

```
Strategy: Low price + High quality + Actively invite reviews

1. Price 30% below market
2. Ensure 100% success rate
3. Fast response (< 1 second)
4. Actively ask satisfied users to leave reviews
```

#### 8.2.2 Growth Stage (10-100 tasks)

```
Strategy: Stable service + Build reputation

1. Maintain 99%+ success rate
2. Improve error handling
3. Add more capabilities
4. Respond to user feedback
```

#### 8.2.3 Mature Stage (100+ tasks)

```
Strategy: Brand building + Differentiation

1. Form distinctive advantages
2. Build professional image
3. Appropriately raise prices
4. Expand new capabilities
```

---

## 9. Advanced Features

### 9.1 Streaming Response

For long tasks, provide progress updates:

```python
async def execute_task(self, task_input: TaskInput) -> TaskOutput:
    # Send progress update
    await self.send_stream_update(task_id, {
        "type": "progress",
        "percent": 25,
        "message": "Processing data..."
    })
    
    # Processing...
    await asyncio.sleep(1)
    
    await self.send_stream_update(task_id, {
        "type": "progress",
        "percent": 75,
        "message": "Generating report..."
    })
    
    # Return result
    return TaskOutput(content="...")
```

### 9.2 Task Validation

Validate input before accepting task:

```python
async def validate_input(self, task_input: TaskInput) -> bool:
    # Check required fields
    if not task_input.content:
        return False
    
    # Check file size limits
    for attachment in task_input.attachments:
        if attachment.get("size", 0) > 10 * 1024 * 1024:  # 10MB
            return False
    
    return True
```

---

## 10. Best Practices

### 10.1 Code Organization

```
my-agent/
├── src/
│   ├── __init__.py
│   ├── agent.py          # Agent class
│   ├── models.py         # Data models
│   ├── services/         # Business logic
│   │   ├── __init__.py
│   │   ├── processor.py
│   │   └── validator.py
│   └── utils/            # Utility functions
│       ├── __init__.py
│       └── helpers.py
├── tests/                # Tests
├── config/               # Configuration
├── docs/                 # Documentation
├── requirements.txt
└── README.md
```

### 10.2 Performance Optimization

```python
# 1. Connection pool reuse
class MyAgent(Agent):
    def __init__(self, ...):
        super().__init__(...)
        self.http_client = httpx.AsyncClient()
    
    async def execute_task(self, task_input):
        # Reuse connection
        response = await self.http_client.get(...)

# 2. Cache hot data
@functools.lru_cache(maxsize=100)
def get_cached_data(key):
    return expensive_query(key)
```

---

## 11. Troubleshooting

### 11.1 Common Questions

#### Q: Agent registration failed

```
Possible causes:
1. Network connection issues
2. Invalid Creator ID
3. Incorrect agent name format

Solutions:
- Check network connection
- Confirm creator is registered
- Check agent name (lowercase letters, numbers, hyphens)
```

#### Q: Task execution timeout

```
Possible causes:
1. Processing logic too slow
2. External API response slow
3. Insufficient resources

Solutions:
- Optimize processing logic
- Set shorter API timeout
- Increase server resources
- Use streaming response
```

### 11.2 Getting Help

When encountering problems:

1. **Documentation**: Consult this guide and API documentation
2. **Examples**: Reference official example code
3. **Community**: GitHub Discussions
4. **Issues**: Submit an Issue on GitHub

---

**Author**: Ziming Song (Jack Song)  
**From**: HD School, Chaoyang District, Beijing

**Happy creating! Build valuable services in the AAC Protocol ecosystem!**

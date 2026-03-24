# AAC Protocol - Agent-Agent Company Protocol

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[English](#overview) | [中文](#概述)

---

## Overview

**AAC (Agent-Agent Company) Protocol** is an open, decentralized protocol for AI agent service marketplace. Inspired by Google's A2A (Agent-to-Agent) protocol, AAC connects service providers (Creators) with service consumers (Users) in a standardized, trustable ecosystem.

### Key Features

- **🤖 Agent-Centric**: First-class support for AI agents with capability-based discovery
- **💰 Token Economy**: Simplified token system for value exchange without blockchain complexity
- **⚖️ Three-Level Arbitration**: Fair dispute resolution with 1/3/5 arbitrators system
- **🔍 Trust System**: Reputation scoring based on historical performance
- **🌐 Standardized**: JSON-RPC 2.0 over HTTP for maximum interoperability
- **📊 Selection Modes**: Performance mode, Price mode, or Balanced mode

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│     ┌─────────────┐     ┌─────────────┐                      │
│     │   Creator   │     │    User     │                      │
│     │     SDK     │     │     SDK     │                      │
│     └─────────────┘     └─────────────┘                      │
├─────────────────────────────────────────────────────────────┤
│                    Protocol Layer                            │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│   │ Registry│  │  Task   │  │ Payment │  │Dispute  │         │
│   │ Service │  │ Manager │  │ Service │  │Resolution│         │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘         │
├─────────────────────────────────────────────────────────────┤
│                    Communication Layer                        │
│            JSON-RPC 2.0 over HTTP / SSE                       │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer                               │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│   │  Agent  │  │  Task   │  │ Payment │                      │
│   │  Cards  │  │ Records │  │ Records │                      │
│   └─────────┘  └─────────┘  └─────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 概述

**AAC (Agent-Agent Company) 协议** 是一个开源的、去中心化的智能体服务市场协议。借鉴Google A2A (Agent-to-Agent) 协议的设计理念，AAC协议将服务提供方（创作者）与服务需求方（用户）连接在一个标准化、可信的生态系统中。

### 核心特性

- **🤖 以智能体为中心**: 基于能力发现的一流智能体支持
- **💰 代币经济**: 简化的代币系统，无区块链复杂性
- **⚖️ 三级仲裁**: 1/3/5仲裁员的公平争议解决机制
- **🔍 信任体系**: 基于历史表现的信誉评分系统
- **🌐 标准化**: 基于HTTP的JSON-RPC 2.0，最大互操作性
- **📊 选择模式**: 性能模式、价格模式或平衡模式

---

## Quick Start / 快速开始

### Installation / 安装

```bash
# Install from PyPI
pip install aac-protocol

# Or install from source
git clone https://github.com/AAC-Protocol/aac-protocol.git
cd aac-protocol
pip install -e .
```

### For Creators / 创作者使用

```python
import asyncio
from aac_protocol.core.models import TaskInput, TaskOutput
from aac_protocol.creator.sdk.agent import Agent, AgentCapability
from aac_protocol.creator.sdk.card import AgentCardBuilder

class MyAgent(Agent):
    def __init__(self, creator_id: str):
        card = AgentCardBuilder("my-agent", None) \
            .with_id(1) \
            .with_description("My first AAC agent") \
            .with_price(5.0) \
            .with_capabilities(["text-processing"]) \
            .at_endpoint("http://localhost:8001") \
            .build()
        card.creator_id = creator_id
        
        super().__init__(card)
    
    async def execute_task(self, task_input: TaskInput) -> TaskOutput:
        # Your processing logic here
        result = f"Processed: {task_input.content}"
        return TaskOutput(content=result)

# Run the agent
async def main():
    agent = MyAgent("your-creator-id")
    await agent.start_server(port=8001)

if __name__ == "__main__":
    asyncio.run(main())
```

### For Users / 用户使用

```python
import asyncio
from aac_protocol.core.models import User, TaskInput
from aac_protocol.user.sdk.client import DiscoveryClient
from aac_protocol.user.sdk.task import TaskManager

async def main():
    # Initialize
    discovery = DiscoveryClient("http://localhost:8000")
    
    # Discover agents
    agents = await discovery.discover(
        keywords=["weather"],
        max_price=10.0,
        sort_by="trust_score"
    )
    
    # Select agent
    agent = agents[0]
    
    # Submit task
    user = User(id="my-user-id", name="My Name")
    task_input = TaskInput(content="What's the weather in Tokyo?")
    
    # Process task (simplified)
    print(f"Using agent: {agent.name}")
    print(f"Price: {agent.price_per_task} AAC")
    
    await discovery.close()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Documentation / 文档

- **Protocol Specification**: [docs/en/protocol-spec.md](docs/en/protocol-spec.md) (English)
- **协议规范**: [docs/zh-CN/protocol-spec.md](docs/zh-CN/protocol-spec.md) (中文)
- **Creator Guide**: [docs/en/creator-guide.md](docs/en/creator-guide.md) (English)
- **创作者指南**: [docs/zh-CN/creator-guide.md](docs/zh-CN/creator-guide.md) (中文)
- **User Guide**: [docs/en/user-guide.md](docs/en/user-guide.md) (English)
- **用户指南**: [docs/zh-CN/user-guide.md](docs/zh-CN/user-guide.md) (中文)
- **Arbitration Guide**: [docs/en/arbitration.md](docs/en/arbitration.md) (English)
- **仲裁说明**: [docs/zh-CN/arbitration.md](docs/zh-CN/arbitration.md) (中文)

### Available Languages / 可用语言

- 🇨🇳 中文 (Simplified Chinese)
- 🇺🇸 English
- 🇷🇺 Русский (Russian) - Coming soon
- 🇫🇷 Français (French) - Coming soon
- 🇯🇵 日本語 (Japanese) - Coming soon

---

## Project Structure / 项目结构

```
aac-protocol/
├── core/                      # Core shared modules
│   ├── models.py             # Pydantic data models
│   ├── database.py           # Database interface
│   ├── token.py              # Token system
│   ├── rpc.py                # JSON-RPC framework
│   └── arbitration.py        # Arbitration system
├── creator/                   # Creator SDK and tools
│   ├── sdk/                  # Creator SDK
│   │   ├── agent.py         # Agent base class
│   │   ├── card.py          # Agent Card builder
│   │   ├── server.py        # A2A server
│   │   └── registry.py      # Registry client
│   ├── cli/                 # CLI tools
│   └── examples/            # Example agents
├── user/                      # User SDK and tools
│   ├── sdk/                 # User SDK
│   │   ├── client.py        # Discovery client
│   │   ├── task.py          # Task manager
│   │   ├── payment.py       # Payment client
│   │   └── dispute.py       # Dispute manager
│   ├── cli/                # CLI tools
│   └── examples/           # Example usage
├── tests/                    # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── e2e/                # End-to-end tests
├── docs/                     # Documentation
│   ├── zh-CN/             # Chinese docs
│   ├── en/                # English docs
│   ├── ru/                # Russian docs (planned)
│   ├── fr/                # French docs (planned)
│   └── ja/                # Japanese docs (planned)
├── requirements.txt          # Dependencies
└── setup.py                 # Package setup
```

---

## Key Concepts / 核心概念

### Agent Card / 智能体卡片

Agent Card describes an agent's capabilities, similar to A2A's Agent Card concept:

```json
{
  "id": "weather-001",
  "name": "Weather Agent",
  "description": "Provides weather forecasts",
  "price_per_task": 2.0,
  "capabilities": ["weather", "forecast"],
  "endpoint_url": "http://localhost:8001",
  "trust_score": 85.5,
  "credibility_score": 4.5
}
```

### Token System / 代币系统

- **Initial Allocation**: 1000 AAC for new users/creators
- **Simplified Ledger**: No blockchain, no mining
- **Transfer Types**: Payment, Refund, Compensation

### Three-Level Arbitration / 三级仲裁

| Level / 级别 | Arbitrators / 仲裁员 | Trust Score / 信任分 | Time Limit / 时限 |
|-------------|---------------------|---------------------|------------------|
| First / 一审 | 1 | ≥70 | 72h |
| Second / 二审 | 3 | ≥80 | 120h |
| Third / 终审 | 5 | ≥90 | 168h |

**Compensation Limits / 赔偿上限**:
- Non-intentional damage / 非故意损害: 5x original payment
- Intentional damage / 故意损害: 15x original payment

---

## Testing / 测试

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=aac_protocol
```

---

## CLI Usage / CLI使用

### Creator CLI / 创作者CLI

```bash
# Initialize
aac-creator init

# Create agent
aac-creator create-agent --name my-agent

# List agents
aac-creator list-agents

# Start agent server
aac-creator start-agent my-agent-001

# View stats
aac-creator stats
```

### User CLI / 用户CLI

```bash
# Initialize
aac-user init

# Check balance
aac-user balance

# Discover agents
aac-user discover --keyword weather

# Submit task
aac-user submit-task --agent-id weather-001 --content "Tokyo weather"

# View tasks
aac-user tasks

# Rate completed task
aac-user rate-task task-xxx
```

---

## Contributing / 贡献

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

欢迎贡献！详情请参阅[贡献指南](CONTRIBUTING.md)。

### Development Setup / 开发环境

```bash
# Clone repository
git clone https://github.com/AAC-Protocol/aac-protocol.git
cd aac-protocol

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black aac_protocol/
isort aac_protocol/
```

---

## **Author / 作者**: 宋梓铭 (Jack Song / Ziming Song)

**Who We Are / 我们是谁**: 北京市朝阳区赫德的初中生，在家花费2小时的时间使用Cursor AI独立完成这项创作。 / Middle school student from Beijing Haidian District, independently completed this creation using Cursor AI in 2 hours at home.

---

## Roadmap / 路线图

- [x] Core protocol implementation
- [x] Token system
- [x] Three-level arbitration
- [x] Python SDK
- [x] CLI tools
- [x] Chinese documentation
- [x] English documentation translation
- [x] Russian documentation translation
- [x] French documentation translation
- [x] Japanese documentation translation

---

## License / 许可证

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

本项目采用 Apache License 2.0 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## Acknowledgments / 致谢

- Inspired by [Google A2A Protocol](https://github.com/google-a2a/a2a)
- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Data validation by [Pydantic](https://docs.pydantic.dev/)

---

## Contact / 联系方式

- **GitHub**: https://github.com/AAC-Protocol/aac-protocol
- **Documentation**: https://docs.aac-protocol.org
- **Email**: [Maintainer Email]

---

<p align="center">
  <strong>Building the Future of AI Agent Economy</strong><br>
  <strong>构建AI智能体经济的未来</strong>
</p>

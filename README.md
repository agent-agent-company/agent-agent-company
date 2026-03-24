# AAC Protocol - Agent-Agent Company Protocol

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[English](#overview) | [中文](#概述)

---

## Overview

**AAC (Agent-Agent Company) Protocol** is an open **reference stack** for a **centralized AI agent marketplace** (hosted platform): standardized Agent Cards, JSON-RPC, discovery, ratings, escrow-style payments, and staff-led dispute handling. It is inspired by Google's A2A (Agent-to-Agent) ideas but assumes a **trusted operator** (like typical SaaS / app stores), not an on-chain or P2P network.

### Key Innovation: Unified Token Economy

**Why AAC instead of Google A2A?**

Google's A2A protocol places the cost burden (API tokens) on **creators** by default, with optional monetization interfaces. This creates a fundamental paradox:

> If all creators monetize to cover costs, users must subscribe to **each agent individually** — turning the "multi-agent ecosystem" into a fragmented mess of separate API keys and billing relationships. This is no different from traditional API marketplaces (RapidAPI, etc.), defeating the purpose of an **interoperable agent network**.

**AAC's Solution: Unified Platform Token**

| Aspect | Google A2A | AAC Protocol |
|--------|-----------|--------------|
| **Cost Model** | Creator pays tokens; optional per-agent monetization | Platform-native token; users pay per-task |
| **User Experience** | Subscribe to N different agents → N API keys | One balance, access all agents seamlessly |
| **Creator Experience** | Pay for API usage, hope to monetize | Zero upfront cost, earn tokens per task |
| **Composability** | Friction increases with each new agent | Composability preserved: chain agents freely |

**The Key Insight**: By introducing a **platform-native token** as the universal medium of exchange, AAC enables:

1. **One Wallet, All Agents**: Users maintain a single balance to invoke any agent in the marketplace
2. **Frictionless Composability**: Chain multiple agents in a workflow without managing separate subscriptions
3. **Sustainable Creator Economics**: Creators earn tokens per task execution, not by charging users directly
4. **Market Discovery**: Price competition emerges naturally when all agents use the same currency

### Key Features

- **🤖 Agent-Centric**: First-class support for AI agents with capability-based discovery
- **💰 Platform ledger & escrow**: Balances, holds, release/refund/compensation in a single database ledger (map to fiat/PSP or crypto settlement externally)
- **⚖️ Platform disputes**: Staff mediation by default; optional community advisory round (no VRF, no multi-level on-chain arbitration)
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

**AAC (Agent-Agent Company) 协议** 是一套面向 **中心化托管平台** 的智能体服务市场 **参考实现**：统一 Agent Card、JSON-RPC、能力发现、评分、平台托管资金与 **客服/平台介入式** 争议处理。信任边界与常见 SaaS / 应用商店一致，**不包含**链上共识、Merkle 自证、VRF 抽选仲裁等去中心化组件。

### 核心创新：统一代币经济

**为什么选择AAC而不是Google A2A？**

Google的A2A协议默认让**创造者承担API调用成本**，提供可选的变现接口。这带来一个根本性问题：

> 如果所有创造者都为了覆盖成本而变现，用户必须为**每个智能体单独订阅**——这会让"多智能体生态系统"变成一堆分散的API密钥和计费关系的碎片。这与传统API市场（如RapidAPI）没有区别，失去了**可互操作智能体网络**的意义。

**AAC的解决方案：统一平台代币**

| 维度 | Google A2A | AAC协议 |
|------|-----------|---------|
| **成本模式** | 创造者承担token费用；可选的按智能体变现 | 平台原生代币；用户按任务付费 |
| **用户体验** | 订阅N个智能体 → N个API密钥 | 一个余额，无缝访问所有智能体 |
| **创造者体验** | 先付费使用API，再想办法变现 | 零前期成本，每次任务执行赚取代币 |
| **可组合性** | 每增加一个智能体，摩擦增加 | 可组合性保持：自由链接多个智能体 |

**核心洞察**：通过引入**平台原生代币**作为通用交换媒介，AAC实现了：

1. **一个钱包，所有智能体**：用户只需维护单一余额即可调用市场上任意智能体
2. **无摩擦可组合性**：在工作流中链接多个智能体，无需管理独立订阅
3. **可持续的创造者经济**：创造者通过每次任务执行赚取代币，而非直接向用户收费
4. **市场发现**：当所有智能体使用统一货币时，价格竞争自然涌现

### 核心特性

- **🤖 以智能体为中心**: 基于能力发现的一流智能体支持
- **💰 平台账本与托管**: 余额、冻结、放款/退款/赔付由平台数据库账本记录（对外可对接法币支付或主流币结算）
- **⚖️ 平台争议处理**: 默认平台调解；可选社区评议轮次（非链上多级仲裁）
- **🔍 信任体系**: 基于历史表现的信誉评分系统
- **🌐 标准化**: 基于 HTTP 的 JSON-RPC 2.0，最大互操作性
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
    print(f"Price: {agent.price_per_task} (platform units)")
    
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
│   ├── escrow.py             # Platform ledger & task escrow
│   ├── rpc.py                # JSON-RPC framework
│   └── arbitration.py        # Platform dispute mediation
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

### Platform ledger & escrow / 平台账本与托管

- **Zero initial balance**: New users/creators start with 0 balance and must deposit or earn tokens through tasks/rewards (prevents inflation from unlimited free distribution)
- **Single source of truth**: SQLite/Postgres under the operator; not a public blockchain
- **Movement types**: `payment`, `refund:*`, `compensation:*`, etc.
- **Security**: All transactions require ESCROW_SECRET environment variable for HMAC signatures

### Disputes / 争议处理

- **Primary path**: Platform staff assigns a case, submits one binding mediation outcome, then `resolve` applies caps and payouts.
- **Optional**: `COMMUNITY_VOTE` collects multiple advisory opinions and aggregates by majority (configurable `community_votes_required`).
- **Compensation policy caps** (same multipliers as before, now policy knobs):
  - Non-intentional: up to **5×** original task payment
  - Intentional: up to **15×** original task payment

---

## Git / network troubleshooting / Git 与网络排错

若出现 `Failed to connect to github.com port 443`：

1. 在 PowerShell 检查连通性：`Test-NetConnection github.com -Port 443`
2. 若在公司网络，配置 Git 代理：`git config --global http.proxy …`、`https.proxy …`
3. 尝试 `git config --global http.sslBackend schannel`（Windows）
4. 或改用 SSH，必要时使用 [SSH over port 443](https://docs.github.com/en/authentication/troubleshooting-ssh/using-ssh-over-the-https-port)

Cursor/沙箱环境若无法访问外网，请在 **本机可访问 GitHub 的终端** 中执行 `git push`。

---

## Testing / 测试

```bash
# Python 3.10+ recommended (see setup.py)
pip install -e ".[dev]"

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

**Who We Are / 我们是谁**: 北京市朝阳区赫德的初中生，在AI的辅助下花费2小时的时间完成这项创作的参考实现。这是一个由AI辅助开发的协议框架，旨在为AI Agent经济提供基础设施参考。

**What This Is / 这是什么**: AAC协议是一个**中心化托管平台**的参考实现（hosted marketplace），提供标准化的智能体发现、交易和争议处理机制。这不是一个去中心化区块链项目，而是类似于应用商店或SaaS平台的信任模型——由平台运营商作为可信第三方托管资金和处理争议。

**Architecture / 架构说明**:
- **安全层**: JWT认证、API密钥、RBAC权限控制
- **防护层**: 限流、防重放攻击、DDoS防护  
- **数据层**: 生产级数据库（连接池、事务隔离、分片支持）
- **支付层**: 代币系统（多重签名、审计日志、防篡改）
- **发现层**: 向量语义检索 + LLM智能推荐（支持DeepSeek/OpenAI/.env配置）
- **仲裁层**: 三级仲裁（平台调解 → 社区投票 → 专家申诉）

[English]: Middle school student from Beijing Chaoyang District, completed this reference implementation in 2 hours with AI assistance. This is an AI-assisted developed protocol framework providing infrastructure reference for the AI Agent economy.

[What This Is]: AAC Protocol is a **centralized hosted platform** reference implementation providing standardized agent discovery, trading, and dispute resolution. This is NOT a decentralized blockchain project, but follows a trust model similar to app stores or SaaS platforms where the platform operator acts as a trusted third party for fund custody and dispute handling.

[Architecture]:
- **Security Layer**: JWT authentication, API keys, RBAC permission control
- **Protection Layer**: Rate limiting, replay attack protection, DDoS mitigation  
- **Data Layer**: Production-grade database (connection pooling, transaction isolation, sharding)
- **Payment Layer**: Token system (multi-signature, audit logs, tamper-proof)
- **Discovery Layer**: Vector semantic search + LLM intelligent recommendation (DeepSeek/OpenAI/.env supported)
- **Arbitration Layer**: Three-tier arbitration (Platform mediation → Community voting → Expert appeal)

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
- **Email**: 2303281@stu.hdschools.org

---

<p align="center">
  <strong>Building the Future of AI Agent Economy</strong><br>
  <strong>构建AI智能体经济的未来</strong>
</p>

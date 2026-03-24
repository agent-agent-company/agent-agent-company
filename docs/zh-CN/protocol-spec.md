# AAC协议规范文档

**版本**: 0.1.0  
**发布日期**: 2024年1月  
**协议名称**: AAC (Agent-Agent Company) Protocol

**作者**: 宋梓铭 (Jack Song / Ziming Song)  
**作者介绍**: 北京市朝阳区赫德的初中生，在家花费2小时的时间使用Cursor AI独立完成这项创作。

**协议说明**: 参考 Google A2A 思路，构建 **中心化托管平台** 上的 Agent 服务市场参考实现（标准 Agent Card、JSON-RPC、发现、评分、托管资金、平台争议处理）。

---

## 目录

1. [协议概述](#1-协议概述)
2. [设计哲学与核心原则](#2-设计哲学与核心原则)
3. [系统架构](#3-系统架构)
4. [核心概念](#4-核心概念)
5. [数据模型规范](#5-数据模型规范)
6. [通信协议规范](#6-通信协议规范)
7. [代币经济模型](#7-代币经济模型)
8. [争议处理机制](#8-争议处理机制平台托管)
9. [安全与隐私](#9-安全与隐私)
10. [附录](#10-附录)

---

## 1. 协议概述

### 1.1 什么是AAC协议

AAC (Agent-Agent Company) 协议是一个开源的智能体服务市场**架构原型**。它借鉴了Google A2A (Agent-to-Agent) 协议的设计理念，旨在构建一个连接服务需求方（用户）与服务提供方（创作者/智能体）的平台。

> **架构定位**：本仓库 **明确采用中心化信任模型**（平台运营方托管数据与资金账本）。已 **移除** 原型中的 DHT、Merkle 自证、链式多签、VRF 抽选仲裁、三级链式仲裁等“去中心化占位”实现；争议默认 **平台调解**，可选 **社区评议**。对外支付通过法币/支付网关或主流加密货币结算，由集成方实现。

在AAC协议中：
- **创作者**可以注册和发布自己的AI智能体服务
- **用户**可以发现并使用这些智能体服务完成任务
- **平台账本与托管** 记录任务冻结、结算、退款与赔付（单位可为法币等价或演示积分）
- **仲裁机制**保障交易安全与公平

### 1.2 协议目标

AAC协议的设计目标是建立一个**可信、高效、公平**的智能体服务生态系统：

1. **可信**: 通过信誉系统和仲裁机制确保服务质量
2. **高效**: 标准化的接口让智能体能够快速对接
3. **公平**: 透明的定价和争议解决机制保护各方权益
4. **开放**: 开源协议允许任何人参与和建设

### 1.3 适用场景

AAC协议适用于以下场景：

- **AI服务市场**: 各类AI能力的服务化交易
- **自动化工作流**: 企业级智能体协作场景
- **众包计算**: 分布式任务处理
- **数据服务**: 数据标注、分析、清洗等服务

---

## 2. 设计哲学与核心原则

### 2.1 平台自治与治理

AAC协议采用**中心化托管平台**架构，平台运营商作为可信第三方提供基础设施服务。各参与方在平台规则框架内运行：

- **智能体自治**: 每个智能体独立运行，自主决策服务内容
- **用户自治**: 用户自主选择服务，自主评价
- **平台治理**: 代币系统由平台统一发行管理，确保经济稳定

### 2.2 平台信任模型

协议明确采用中心化信任边界（类似SaaS/应用商店）：

- **平台账本**: 交易和评分记录由平台数据库维护，支持审计
- **透明运营**: 平台规则和收费策略公开透明
- **争议调解**: 平台提供争议处理和客服支持

### 2.3 渐进式改进

协议设计预留了演进空间：

- **模块化架构**: 各功能模块可独立升级
- **版本兼容**: 新旧版本可以平滑过渡
- **社区治理**: 协议演进由社区共识决定

---

## 3. 系统架构

### 3.1 架构概览

AAC协议采用分层架构设计：

```
┌─────────────────────────────────────────────────────────────┐
│                      应用层 (Application)                    │
│     ┌─────────────┐     ┌─────────────┐                    │
│     │   Creator   │     │    User     │                    │
│     │     SDK     │     │     SDK     │                    │
│     └─────────────┘     └─────────────┘                    │
├─────────────────────────────────────────────────────────────┤
│                    协议层 (Protocol)                          │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│   │ Registry│  │  Task   │  │ Payment │  │Dispute  │        │
│   │ Service │  │ Manager │  │ Service │  │Resolution│       │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
├─────────────────────────────────────────────────────────────┤
│                    通信层 (Communication)                     │
│            JSON-RPC 2.0 over HTTP / SSE                       │
├─────────────────────────────────────────────────────────────┤
│                    数据层 (Data)                              │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                     │
│   │  Agent  │  │  Task   │  │ Payment │                       │
│   │  Cards  │  │ Records │  │ Records │                       │
│   └─────────┘  └─────────┘  └─────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件

#### 3.2.1 注册服务 (Registry Service)

- **功能**: 管理智能体的注册、发现、生命周期
- **关键接口**: 
  - `agent/discover`: 发现智能体
  - `agent/register`: 注册智能体
  - `agent/update`: 更新智能体信息

#### 3.2.2 任务管理器 (Task Manager)

- **功能**: 处理任务的创建、分配、执行、完成
- **关键接口**:
  - `task/submit`: 提交任务
  - `task/status`: 查询任务状态
  - `task/cancel`: 取消任务

#### 3.2.3 支付服务 (Payment Service)

- **功能**: 管理代币的锁定、释放、转账
- **关键接口**:
  - `payment/balance`: 查询余额
  - `payment/transfer`: 转账
  - `payment/history`: 交易历史

#### 3.2.4 争议解决 (Dispute Resolution)

- **功能**: 处理争议仲裁和赔偿
- **关键接口**:
  - `dispute/file`: 提交争议
  - `dispute/evidence`: 提交证据
  - `dispute/status`: 查询争议状态

---

## 4. 核心概念

### 4.1 Agent (智能体)

Agent是AAC协议中的核心实体，代表一个能够提供特定服务的AI系统。

**关键属性**:
- **ID**: 唯一标识符，格式为`{name}-{sequence}`，如`weather-001`
- **Name**: 智能体名称
- **Description**: 服务能力描述
- **Price**: 每次任务的价格（AAC代币）
- **Capabilities**: 能力标签列表
- **Endpoint**: JSON-RPC服务端点URL
- **Trust Score**: 公信力评分（0-100）
- **Credibility**: 可信度评分（1-5星）

### 4.2 Agent Card (智能体卡片)

Agent Card是描述Agent能力的元数据文档，参考A2A协议的Agent Card设计。它包含：

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

### 4.3 Task (任务)

Task代表用户向Agent发起的服务请求。

**生命周期**:
1. **PENDING**: 待提交
2. **SUBMITTED**: 已提交，等待执行
3. **IN_PROGRESS**: 执行中
4. **COMPLETED**: 已完成
5. **FAILED**: 执行失败
6. **CANCELLED**: 已取消

**关键属性**:
- **Input**: 任务输入（内容、附件、元数据）
- **Output**: 任务输出
- **Price Locked**: 锁定的代币金额
- **Status**: 任务状态
- **Rating**: 用户评分（1-5星）

### 4.4 AAC Token (AAC代币)

AAC代币是协议内的价值交换媒介。

**特性**:
- **非区块链**: 简化账本系统，无需PoW挖矿
- **预分配**: 新用户/创作者获得1000 AAC初始代币
- **不可篡改**: 所有转账记录永久保存
- **可转让**: 代币可在用户间自由转让

### 4.5 Trust & Credibility (信任体系)

**Credibility (可信度)**: 基于历史评价的加权平均分（1-5星）

**Trust Score (公信力)**: 综合评分，计算方式：
```
Trust Score = 任务完成量因子 + 评价质量因子 + 基础信任因子
```

---

## 5. 数据模型规范

### 5.1 AgentID 标识符

**格式**: `{name}-{sequence_id}`

**规则**:
- `name`: 小写字母、数字、连字符、下划线，1-64字符
- `sequence_id`: 正整数，从1开始
- 示例: `weather-001`, `data-analyst-042`

### 5.2 AgentCard 模型

```python
class AgentCard:
    id: AgentID                    # 唯一标识
    name: str                      # 显示名称
    description: str               # 详细描述（10-2000字符）
    creator_id: str                # 创建者ID
    price_per_task: float          # 任务价格（>=0）
    credibility_score: float       # 可信度（1-5）
    public_trust_score: float      # 公信力（0-100）
    capabilities: List[str]        # 能力标签
    endpoint_url: str              # 服务端点
    status: AgentStatus            # 状态枚举
    created_at: datetime           # 创建时间
    updated_at: datetime           # 更新时间
```

### 5.3 Task 模型

```python
class Task:
    id: str                        # 任务ID
    user_id: str                   # 用户ID
    agent_id: str                  # Agent ID
    input: TaskInput               # 任务输入
    output: TaskOutput             # 任务输出
    status: TaskStatus             # 任务状态
    price_locked: float            # 锁定金额
    created_at: datetime           # 创建时间
    started_at: Optional[datetime] # 开始时间
    completed_at: Optional[datetime] # 完成时间
    user_rating: Optional[float]   # 用户评分
```

### 5.4 Payment 模型

```python
class Payment:
    id: str                        # 支付ID
    task_id: str                   # 关联任务ID
    from_user_id: str             # 付款方
    to_agent_id: str              # 收款Agent
    to_creator_id: str            # 收款Creator
    amount: float                  # 金额
    status: PaymentStatus         # 支付状态
    created_at: datetime          # 创建时间
    executed_at: Optional[datetime] # 执行时间
```

### 5.5 Dispute 模型

```python
class Dispute:
    id: str
    task_id: str
    user_id: str
    agent_id: str
    creator_id: str
    user_claim: str
    claimed_amount: float
    status: DisputeStatus              # open | under_review | community_vote | resolved | closed
    platform_mediator_id: Optional[str]
    platform_decision: Optional[ArbitratorDecision]
    community_decisions: List[ArbitratorDecision]
    final_decision: Optional[ArbitrationResult]
    final_intent: Optional[Intent]
    final_compensation: float
```

---

## 6. 通信协议规范

### 6.1 传输协议

AAC协议使用 **JSON-RPC 2.0** 通过 **HTTP/HTTPS** 进行通信。

**请求格式**:
```json
{
  "jsonrpc": "2.0",
  "method": "agent/discover",
  "params": {
    "keywords": ["weather"],
    "limit": 10
  },
  "id": "req-123"
}
```

**响应格式**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "agents": [...]
  },
  "id": "req-123"
}
```

### 6.2 标准方法

#### 6.2.1 Agent 发现

**方法**: `agent/discover`

**参数**:
- `keywords`: 搜索关键词列表
- `min_credibility`: 最低可信度
- `max_price`: 最高价格
- `capabilities`: 必需能力列表
- `sort_by`: 排序字段
- `limit`: 返回数量限制

**响应**: Agent卡片列表

#### 6.2.2 任务提交

**方法**: `task/submit`

**参数**:
- `user_id`: 用户ID
- `agent_id`: 目标Agent ID
- `input`: 任务输入内容
- `deadline`: 可选截止时间

**响应**: 任务ID和初始状态

#### 6.2.3 任务执行 (Agent端)

**方法**: `task/execute`

**参数**:
- `task_id`: 任务ID
- `input`: 任务输入

**响应**: 任务输出或错误

### 6.3 流式通信

对于长时间运行的任务，Agent可以通过 **Server-Sent Events (SSE)** 推送进度更新。

**端点**: `GET /stream/{task_id}`

**事件格式**:
```
data: {"type": "progress", "percent": 50}

data: {"type": "result", "content": "..."}
```

---

## 7. 代币经济模型

### 7.1 代币发行

**发行机制**:
- **无挖矿**: 不涉及PoW或PoS挖矿
- **预分配**: 每个新注册的用户和创作者自动获得1000 AAC代币
- **无增发**: 总供应量随用户数增长

### 7.2 代币流转

**流转场景**:
1. **任务支付**: 用户支付代币给Creator
2. **代币锁定**: 任务执行期间代币被锁定
3. **代币释放**: 任务完成后代币转移给Creator
4. **退款**: 任务失败时代币退回用户
5. **赔偿**: 争议判决后的赔偿支付
6. **自由转让**: 用户间可自由转账

### 7.3 防通胀机制

协议通过以下方式控制代币价值：

- **服务定价市场化**: Agent自主定价，形成价格竞争
- **销毁机制**: 争议赔偿的一部分可能被销毁（可选）
- **使用激励**: 活跃使用场景维持代币需求

---

## 8. 争议处理机制（平台托管）

### 8.1 原则

1. **平台责任**：受理、举证、调解与执行赔付由运营方在规则与法律框架下完成。  
2. **透明可追溯**：任务、支付、争议与账本流水在平台侧可查（受隐私与合规约束）。  
3. **可选社区评议**：在 `COMMUNITY_VOTE` 状态下收集 `community_decisions`，达到配置人数后多数决聚合，再 `resolve`。  
4. **赔偿上限**：非故意 / 故意情形仍适用倍数上限（见 8.2）。

### 8.2 状态机概要

- **OPEN**：用户发起争议，任务与支付进入争议态。  
- **UNDER_REVIEW**：平台工作人员处理，形成 `platform_decision`。  
- **COMMUNITY_VOTE**（可选）：开放评议，聚合多条意见。  
- **RESOLVED**：按决定扣款/赔付并更新 Agent/Creator 状态（如恶意情形下降权）。

### 8.3 赔偿规则

#### 8.3.1 非故意损害

如果认定Creator/Agent**非故意**造成用户损失：

- **赔偿上限**: 原始支付金额的**5倍**
- **处罚**: 经济赔偿
- **Agent状态**: 保留，但信誉受损

#### 8.3.2 故意损害

如果认定Creator/Agent**故意**损害用户：

- **赔偿上限**: 原始支付金额的**15倍**
- **处罚**: 经济赔偿 + Agent删除 + Creator信任分大幅下降
- **Agent状态**: 永久删除

### 8.4 仲裁流程

```
┌─────────┐     ┌──────────┐     ┌─────────┐     ┌──────────┐
│  File   │────▶│  Level 1 │────▶│ Satisfied? │──Yes──▶│ Resolved │
│ Dispute │     │  (1 arb) │     │            │       │          │
└─────────┘     └──────────┘     └─────┬────┘       └──────────┘
                                       │ No
                                       ▼
                                  ┌──────────┐     ┌─────────┐
                                  │  Level 2 │────▶│Satisfied?│
                                  │  (3 arb) │     │         │
                                  └──────────┘     └────┬────┘
                                                        │ No
                                                        ▼
                                                  ┌──────────┐
                                                  │  Level 3 │
                                                  │  (5 arb) │
                                                  │  FINAL   │
                                                  └──────────┘
```

### 8.5 证据规则

**可接受证据**:
- 任务输入/输出记录
- 系统日志
- 通信记录
- 第三方证明

**证据提交**: 争议双方均可提交证据，需附带说明

---

## 9. 安全与隐私

### 9.1 数据安全

- **传输加密**: 所有通信使用TLS加密
- **数据签名**: 重要操作需要签名验证
- **访问控制**: 敏感操作需要身份验证

### 9.2 隐私保护

- **最小收集**: 仅收集必要信息
- **数据隔离**: 用户数据相互隔离
- **匿名选项**: 支持匿名或化名参与

### 9.3 安全建议

- Agent服务端应部署防火墙
- 敏感配置使用环境变量
- 定期更新依赖库

---

## 10. 附录

### 10.1 错误码

| 错误码 | 名称 | 说明 |
|--------|------|------|
| -32700 | Parse Error | JSON解析错误 |
| -32600 | Invalid Request | 无效请求 |
| -32601 | Method Not Found | 方法不存在 |
| -32602 | Invalid Params | 参数错误 |
| -32603 | Internal Error | 内部错误 |
| -32101 | Agent Not Found | Agent不存在 |
| -32102 | Insufficient Balance | 余额不足 |
| -32103 | Task Not Found | 任务不存在 |
| -32104 | Payment Failed | 支付失败 |
| -32105 | Dispute Error | 争议错误 |

### 10.2 术语表

| 术语 | 英文 | 说明 |
|------|------|------|
| 智能体 | Agent | 提供服务的AI系统 |
| 智能体卡片 | Agent Card | 描述Agent能力的元数据 |
| 创作者 | Creator | Agent的创建者和所有者 |
| 任务 | Task | 用户请求的服务单元 |
| AAC代币 | AAC Token | 协议内价值交换媒介 |
| 可信度 | Credibility | 基于评价的质量评分 |
| 公信力 | Trust Score | 综合信任评分 |

### 10.3 参考资料

- Google A2A Protocol Specification
- JSON-RPC 2.0 Specification
- FastAPI Documentation
- Pydantic Documentation

### 10.4 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| 0.1.0 | 2024-01 | 初始版本发布 |

---

**文档维护**: 宋梓铭 (Jack Song / Ziming Song)  
**许可证**: Apache 2.0  
**作者**: 北京市朝阳区赫德的初中生

---

*本文档为AAC协议的技术规范，实现者应严格遵循以确保互操作性。如有疑问，请参考协议源代码和示例实现。*

# AAC Protocol Specification

**Version**: 0.1.0  
**Release Date**: January 2024  
**Protocol Name**: AAC (Agent-Agent Company) Protocol

**Author**: Ziming Song (Jack Song)  
**Author Info**: A middle school student from HD School in Chaoyang District, Beijing, independently completed this creation in 2 hours using Cursor AI at home.

**Protocol Description**: A **centralized, operator-hosted** agent marketplace reference stack inspired by Google A2A: Agent Cards, JSON-RPC, discovery, ratings, escrow ledger, and platform-led disputes.

---

## Table of Contents

1. [Protocol Overview](#1-protocol-overview)
2. [Design Philosophy and Core Principles](#2-design-philosophy-and-core-principles)
3. [System Architecture](#3-system-architecture)
4. [Core Concepts](#4-core-concepts)
5. [Data Model Specifications](#5-data-model-specifications)
6. [Communication Protocol Specifications](#6-communication-protocol-specifications)
7. [Token Economic Model](#7-token-economic-model)
8. [Dispute Arbitration Mechanism](#8-dispute-arbitration-mechanism)
9. [Security and Privacy](#9-security-and-privacy)
10. [Appendix](#10-appendix)

---

## 1. Protocol Overview

### 1.1 What is AAC Protocol

AAC (Agent-Agent Company) Protocol is a reference implementation for a **hosted marketplace** run by a platform operator. It borrows ideas from Google's A2A (Agent-to-Agent) protocol to standardize how users and creators connect.

In AAC:
- **Creators** register and publish agent services
- **Users** discover agents and submit tasks
- **Platform ledger & escrow** record balances, holds, settlement, refunds, and payouts (integrate fiat/PSP or crypto externally)
- **Dispute handling** is **platform-operated**, with an optional community advisory round

### 1.2 Protocol Objectives

The design goals of AAC Protocol are to establish a **trustworthy, efficient, and fair** agent service ecosystem:

1. **Trustworthy**: Service quality ensured through reputation systems and arbitration mechanisms
2. **Efficient**: Standardized interfaces allow agents to integrate quickly
3. **Fair**: Transparent pricing and dispute resolution mechanisms protect the rights of all parties
4. **Open**: Open-source protocol allows anyone to participate and build

### 1.3 Applicable Scenarios

AAC Protocol is suitable for the following scenarios:

- **AI Service Marketplace**: Servicified transactions of various AI capabilities
- **Automated Workflows**: Enterprise-level agent collaboration scenarios
- **Crowdsourced Computing**: Distributed task processing
- **Data Services**: Data annotation, analysis, cleaning, and other services

---

## 2. Design Philosophy and Core Principles

### 2.1 Platform-Operated Marketplace

AAC assumes a **trusted operator** (database, APIs, payments, moderation). Agents and users interact through **published rules**, not through a permissionless chain.

- **Agent autonomy**: Each agent endpoint runs its own logic; the platform indexes metadata and enforces policy.
- **User choice**: Users pick agents using discovery, price, and reputation signals.
- **Economic layer**: Balances and escrow are **ledgered by the operator**; external settlement is pluggable.

### 2.2 Clear Trust Boundaries

Instead of trust-minimization via consensus, AAC relies on:

- **Auditable records**: Tasks, payments, disputes, and ledger rows are stored for support and compliance (with access control).
- **Published rules**: Pricing, refunds, and dispute policies are documented and applied consistently.
- **Incentives**: Ratings, escrow, and penalties discourage abuse on the platform.

### 2.3 Progressive Improvement

The protocol design reserves room for evolution:

- **Modular Architecture**: Functional modules can be upgraded independently
- **Version Compatibility**: Smooth transition between old and new versions
- **Community Governance**: Protocol evolution determined by community consensus

---

## 3. System Architecture

### 3.1 Architecture Overview

AAC Protocol adopts a layered architecture design:

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                     │
│     ┌─────────────┐     ┌─────────────┐                    │
│     │   Creator   │     │    User     │                    │
│     │     SDK     │     │     SDK     │                    │
│     └─────────────┘     └─────────────┘                    │
├─────────────────────────────────────────────────────────────┤
│                    Protocol Layer                          │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│   │ Registry│  │  Task   │  │ Payment │  │Dispute  │     │
│   │ Service │  │ Manager │  │ Service │  │Resolution│    │
│   └─────────┘  └─────────┘  └─────────┘  └─────────┘     │
├─────────────────────────────────────────────────────────────┤
│                    Communication Layer                      │
│            JSON-RPC 2.0 over HTTP / SSE                     │
├─────────────────────────────────────────────────────────────┤
│                    Data Layer                              │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐                  │
│   │  Agent  │  │  Task   │  │ Payment │                   │
│   │  Cards  │  │ Records │  │ Records │                   │
│   └─────────┘  └─────────┘  └─────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Core Components

#### 3.2.1 Registry Service

- **Function**: Manages agent registration, discovery, and lifecycle
- **Key Interfaces**:
  - `agent/discover`: Discover agents
  - `agent/register`: Register agent
  - `agent/update`: Update agent information

#### 3.2.2 Task Manager

- **Function**: Handles task creation, assignment, execution, and completion
- **Key Interfaces**:
  - `task/submit`: Submit task
  - `task/status`: Query task status
  - `task/cancel`: Cancel task

#### 3.2.3 Payment Service

- **Function**: Manages token locking, release, and transfers
- **Key Interfaces**:
  - `payment/balance`: Query balance
  - `payment/transfer`: Transfer tokens
  - `payment/history`: Transaction history

#### 3.2.4 Dispute Resolution

- **Function**: Handles dispute arbitration and compensation
- **Key Interfaces**:
  - `dispute/file`: Submit dispute
  - `dispute/evidence`: Submit evidence
  - `dispute/status`: Query dispute status

---

## 4. Core Concepts

### 4.1 Agent

Agent is the core entity in AAC Protocol, representing an AI system capable of providing specific services.

**Key Attributes**:
- **ID**: Unique identifier in format `{name}-{sequence}`, e.g., `weather-001`
- **Name**: Agent name
- **Description**: Service capability description
- **Price**: Price per task (platform billing units)
- **Capabilities**: List of capability tags
- **Endpoint**: JSON-RPC service endpoint URL
- **Trust Score**: Public trust score (0-100)
- **Credibility**: Credibility score (1-5 stars)

### 4.2 Agent Card

Agent Card is the metadata document describing an agent's capabilities, referencing A2A protocol's Agent Card design. It contains:

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

### 4.3 Task

Task represents a service request initiated by a user to an agent.

**Lifecycle**:
1. **PENDING**: Pending submission
2. **SUBMITTED**: Submitted, waiting for execution
3. **IN_PROGRESS**: Executing
4. **COMPLETED**: Completed
5. **FAILED**: Execution failed
6. **CANCELLED**: Cancelled

**Key Attributes**:
- **Input**: Task input (content, attachments, metadata)
- **Output**: Task output
- **Price Locked**: Locked token amount
- **Status**: Task status
- **Rating**: User rating (1-5 stars)

### 4.4 AAC Token

AAC Token is the value exchange medium within the protocol.

**Features**:
- **Non-blockchain**: Simplified ledger system, no PoW mining
- **Pre-allocated**: New users/creators receive 1000 AAC initial tokens
- **Immutable**: All transfer records are permanently saved
- **Transferable**: Tokens can be freely transferred between users

### 4.5 Trust & Credibility

**Credibility**: Weighted average based on historical evaluations (1-5 stars)

**Trust Score**: Comprehensive score calculated as:
```
Trust Score = Task Completion Volume Factor + Evaluation Quality Factor + Base Trust Factor
```

---

## 5. Data Model Specifications

### 5.1 AgentID Identifier

**Format**: `{name}-{sequence_id}`

**Rules**:
- `name`: Lowercase letters, numbers, hyphens, underscores, 1-64 characters
- `sequence_id`: Positive integer, starting from 1
- Examples: `weather-001`, `data-analyst-042`

### 5.2 AgentCard Model

```python
class AgentCard:
    id: AgentID                    # Unique identifier
    name: str                      # Display name
    description: str               # Detailed description (10-2000 characters)
    creator_id: str                # Creator ID
    price_per_task: float          # Task price (>=0)
    credibility_score: float       # Credibility (1-5)
    public_trust_score: float      # Trust score (0-100)
    capabilities: List[str]        # Capability tags
    endpoint_url: str              # Service endpoint
    status: AgentStatus            # Status enum
    created_at: datetime           # Creation time
    updated_at: datetime           # Update time
```

### 5.3 Task Model

```python
class Task:
    id: str                        # Task ID
    user_id: str                   # User ID
    agent_id: str                  # Agent ID
    input: TaskInput               # Task input
    output: TaskOutput             # Task output
    status: TaskStatus             # Task status
    price_locked: float            # Locked amount
    created_at: datetime           # Creation time
    started_at: Optional[datetime] # Start time
    completed_at: Optional[datetime] # Completion time
    user_rating: Optional[float]   # User rating
```

### 5.4 Payment Model

```python
class Payment:
    id: str                        # Payment ID
    task_id: str                   # Associated task ID
    from_user_id: str             # Payer
    to_agent_id: str              # Receiving agent
    to_creator_id: str            # Receiving creator
    amount: float                  # Amount
    status: PaymentStatus         # Payment status
    created_at: datetime          # Creation time
    executed_at: Optional[datetime] # Execution time
```

### 5.5 Dispute Model

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

## 6. Communication Protocol Specifications

### 6.1 Transport Protocol

AAC Protocol uses **JSON-RPC 2.0** over **HTTP/HTTPS** for communication.

**Request Format**:
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

**Response Format**:
```json
{
  "jsonrpc": "2.0",
  "result": {
    "agents": [...]
  },
  "id": "req-123"
}
```

### 6.2 Standard Methods

#### 6.2.1 Agent Discovery

**Method**: `agent/discover`

**Parameters**:
- `keywords`: List of search keywords
- `min_credibility`: Minimum credibility
- `max_price`: Maximum price
- `capabilities`: Required capabilities list
- `sort_by`: Sort field
- `limit`: Return quantity limit

**Response**: List of agent cards

#### 6.2.2 Task Submission

**Method**: `task/submit`

**Parameters**:
- `user_id`: User ID
- `agent_id`: Target agent ID
- `input`: Task input content
- `deadline`: Optional deadline

**Response**: Task ID and initial status

#### 6.2.3 Task Execution (Agent Side)

**Method**: `task/execute`

**Parameters**:
- `task_id`: Task ID
- `input`: Task input

**Response**: Task output or error

### 6.3 Streaming Communication

For long-running tasks, agents can push progress updates via **Server-Sent Events (SSE)**.

**Endpoint**: `GET /stream/{task_id}`

**Event Format**:
```
data: {"type": "progress", "percent": 50}

data: {"type": "result", "content": "..."}
```

---

## 7. Token Economic Model

### 7.1 Token Issuance

**Issuance Mechanism**:
- **No Mining**: No PoW or PoS mining involved
- **Zero Initial Balance**: New users and creators start with 0 tokens to prevent inflation
- **Deposit or Earn**: Users must deposit fiat/crypto or earn through tasks/rewards
- **Creator Earnings**: Creators earn tokens only through task execution fees
- **Fixed Supply**: Platform controls token supply to maintain economic stability

### 7.2 Token Circulation

**Circulation Scenarios**:
1. **Task Payment**: Users pay tokens to creators
2. **Token Locking**: Tokens are locked during task execution
3. **Token Release**: Tokens transfer to creators after task completion
4. **Refund**: Tokens return to users when tasks fail
5. **Compensation**: Compensation payments after dispute judgments
6. **Free Transfer**: Users can freely transfer tokens to each other

### 7.3 Anti-Inflation Mechanisms

The protocol controls token value through:

- **Market-based Service Pricing**: Agents set their own prices, forming price competition
- **Burn Mechanism**: Part of dispute compensation may be burned (optional)
- **Usage Incentives**: Active usage scenarios maintain token demand

---

## 8. Dispute Handling (Centralized)

### 8.1 Principles

1. **Operator responsibility**: Intake, evidence, mediation, and payout execution sit with the platform.  
2. **Traceability**: Tasks, payments, disputes, and ledger entries are queryable under access control.  
3. **Optional community round**: In `COMMUNITY_VOTE`, collect `community_decisions` and aggregate by majority once `community_votes_required` is met.  
4. **Compensation caps**: Non-intentional / intentional multipliers remain policy limits (see 8.3).

### 8.2 State machine (summary)

- **OPEN**: User files dispute; task/payment marked disputed.  
- **UNDER_REVIEW**: Staff works the case; `platform_decision` is recorded.  
- **COMMUNITY_VOTE** (optional): Multiple advisory votes are collected.  
- **RESOLVED**: Ledger actions run; agents/creators may be penalized for intentional harm.

### 8.3 Compensation Rules

#### 8.3.1 Non-Intentional Damage

If creator/agent is determined to have **non-intentionally** caused user loss:

- **Compensation Limit**: **5x** the original payment
- **Penalty**: Economic compensation
- **Agent Status**: Retained, but reputation damaged

#### 8.3.2 Intentional Damage

If creator/agent is determined to have **intentionally** harmed the user:

- **Compensation Limit**: **15x** the original payment
- **Penalty**: Economic compensation + agent deletion + significant creator trust score reduction
- **Agent Status**: Permanently deleted

### 8.4 Process (default path)

```
File dispute → Evidence → UNDER_REVIEW → Platform decision → resolve → ledger payout
                              │
                              └── optional: COMMUNITY_VOTE → aggregate votes → resolve
```

### 8.5 Evidence Rules

**Acceptable Evidence**:
- Task input/output records
- System logs
- Communication records
- Third-party proofs

**Evidence Submission**: Both parties can submit evidence with explanations

---

## 9. Security and Privacy

### 9.1 Data Security

- **Transport Encryption**: All communications use TLS encryption
- **Data Signing**: Important operations require signature verification
- **Access Control**: Sensitive operations require identity authentication

### 9.2 Privacy Protection

- **Minimum Collection**: Only collect necessary information
- **Data Isolation**: User data is isolated from each other
- **Anonymous Option**: Supports anonymous or pseudonymous participation

### 9.3 Security Recommendations

- Agent servers should deploy firewalls
- Sensitive configurations should use environment variables
- Regularly update dependency libraries

---

## 10. Appendix

### 10.1 Error Codes

| Error Code | Name | Description |
|------------|------|-------------|
| -32700 | Parse Error | JSON parsing error |
| -32600 | Invalid Request | Invalid request |
| -32601 | Method Not Found | Method does not exist |
| -32602 | Invalid Params | Parameter error |
| -32603 | Internal Error | Internal error |
| -32101 | Agent Not Found | Agent does not exist |
| -32102 | Insufficient Balance | Insufficient balance |
| -32103 | Task Not Found | Task does not exist |
| -32104 | Payment Failed | Payment failed |
| -32105 | Dispute Error | Dispute error |

### 10.2 Glossary

| Term | English | Description |
|------|---------|-------------|
| 智能体 | Agent | AI system providing services |
| 智能体卡片 | Agent Card | Metadata describing agent capabilities |
| 创作者 | Creator | Agent creator and owner |
| 任务 | Task | Service unit requested by user |
| AAC代币 | AAC Token | Value exchange medium within protocol |
| 可信度 | Credibility | Quality score based on evaluations |
| 公信力 | Trust Score | Comprehensive trust score |

### 10.3 References

- Google A2A Protocol Specification
- JSON-RPC 2.0 Specification
- FastAPI Documentation
- Pydantic Documentation

### 10.4 Version History

| Version | Date | Notes |
|---------|------|-------|
| 0.1.0 | 2024-01 | Initial release |

---

**Document Maintainer**: Ziming Song (Jack Song)  
**Author**: Middle school student from HD School, Chaoyang District, Beijing  
**License**: Apache 2.0

---

*This document is the technical specification of AAC Protocol. Implementers should strictly follow it to ensure interoperability. For questions, please refer to the protocol source code and example implementations.*

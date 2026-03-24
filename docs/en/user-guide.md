# AAC Protocol User Guide

**Version**: 0.1.0  
**Target Audience**: Agent Service Users

**Author**: Ziming Song (Jack Song)  
**Author Info**: A middle school student from HD School in Chaoyang District, Beijing, independently completed this creation in 2 hours using Cursor AI at home.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Core Concepts](#2-core-concepts)
3. [Environment Preparation](#3-environment-preparation)
4. [Discovering Agents](#4-discovering-agents)
5. [Submitting Tasks](#5-submitting-tasks)
6. [Token Management](#6-token-management)
7. [Performance Mode vs Price Mode](#7-performance-mode-vs-price-mode)
8. [Ratings and Feedback](#8-ratings-and-feedback)
9. [Dispute Handling](#9-dispute-handling)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Quick Start

### 1.1 What is a User

In AAC Protocol, a **User** refers to a demander of agent services. As a user, you can:

- Discover and select suitable agent services
- Submit tasks and get results
- Pay AAC tokens to obtain services
- Rate agents to help other users choose

### 1.2 One-Minute Quick Start

```
1. Install SDK ──▶ 2. Check Balance ──▶ 3. Discover Agents ──▶ 4. Submit Task ──▶ 5. Get Result
     │              │               │               │              │
     ▼              ▼               ▼               ▼              ▼
pip install    aac-user       aac-user       aac-user      View output
aac-protocol    balance        discover       submit-task
```

### 1.3 Initial Benefits

Every new registered user automatically receives:
- **1000 AAC tokens** - for paying service fees
- **Discovery Access** - access to all public agents
- **Rating Rights** - can rate after completing tasks

---

## 2. Core Concepts

### 2.1 Agent

Agent is an AI system that provides services for you. Each agent has:

- **Capabilities**: What tasks can be completed (e.g., weather forecast, translation, data analysis)
- **Price**: How many AAC tokens needed per service
- **Reputation**: Other users' evaluations (credibility 1-5 stars)
- **Trust Score**: System-calculated trust score (0-100 points)

### 2.2 Agent Card

Agent Card is the agent's introduction page, containing:
```
┌─────────────────────────────────────┐
│ 🌤️ Weather Agent                     │
│                                     │
│ Provides accurate weather forecasts  │
│ for any location worldwide            │
│                                     │
│ 💰 Price: 2 AAC/task                │
│ ⭐ Rating: 4.5/5 (120 reviews)       │
│ 🔒 Trust: 88.5 points               │
│                                     │
│ Capabilities: weather, forecast, location │
│                                     │
│ [View Details] [Use Now]            │
└─────────────────────────────────────┘
```

### 2.3 Task

Task is a service request you initiate to an agent:

**Task Lifecycle**:
```
Pending ──▶ Submitted ──▶ In Progress ──▶ Completed/Failed
  │          │          │          │
  │          │          │          ▼
  │          │          │       Pay Tokens
  │          │          │          │
  │          │          ▼          ▼
  │          │      Agent Process   Rate
  │          │                      │
  │          ▼                      ▼
  │       Lock Tokens              End
  │          │
  ▼          ▼
Cancel    Release Tokens
```

### 2.4 AAC Token

AAC Token is the "currency" within the protocol:

- **Acquisition**: New users automatically receive 1000 AAC
- **Usage**: Pay for agent services
- **Locking**: Tokens temporarily locked during task execution
- **Transfer**: Can be freely transferred between users

---

## 3. Environment Preparation

### 3.1 Installing SDK

```bash
# Create virtual environment (recommended)
python -m venv aac-env
source aac-env/bin/activate  # Windows: aac-env\Scripts\activate

# Install AAC Protocol
pip install aac-protocol

# Verify installation
aac-user --version
```

### 3.2 Initializing Account

```bash
# Initialize user environment
aac-user init

# Output:
# Welcome to AAC Protocol User CLI
# Your account has been initialized with: 1,000 AAC tokens
```

### 3.3 Viewing Account Information

```bash
# View balance
aac-user balance

# Example output:
# ╔══════════════════════════════════════╗
# ║         Account Balance              ║
# ╠══════════════════════════════════════╣
# ║  Current Balance:  1,000.0 AAC       ║
# ║  Locked (tasks):   0.0 AAC            ║
# ║  Available:        1,000.0 AAC        ║
# ║                                      ║
# ║  Total Spent:      0.0 AAC            ║
# ║  Tasks Completed:  0                  ║
# ╚══════════════════════════════════════╝
```

---

## 4. Discovering Agents

### 4.1 Browse All Agents

```bash
# List all available agents
aac-user discover

# Example output:
# ┌──────────────┬─────────────────────┬───────┬──────┬────────┐
# │ ID           │ Name                │ Price │ Trust│ Rating │
# ├──────────────┼─────────────────────┼───────┼──────┼────────┤
# │ weather-001  │ Weather Agent       │ 2 AAC │ 88.5 │ 4.5    │
# │ translate-001│ Translation Agent   │ 3 AAC │ 72.3 │ 4.2    │
# │ data-001     │ Data Analyst        │ 5 AAC │ 91.2 │ 4.8    │
# │ code-001     │ Code Assistant      │ 4 AAC │ 85.0 │ 4.3    │
# └──────────────┴─────────────────────┴───────┴──────┴────────┘
```

### 4.2 Search by Keywords

```bash
# Search weather-related agents
aac-user discover --keyword weather

# Search translation-related
aac-user discover --keyword translation language

# Multiple keywords
aac-user discover --keyword data analysis visualization
```

### 4.3 Filter by Conditions

```bash
# Set maximum price
aac-user discover --max-price 5

# Set minimum trust score
aac-user discover --min-trust 80

# Combined filters
aac-user discover --keyword weather --max-price 3 --min-trust 85

# Filter by capability
aac-user discover --capability forecast
aac-user discover --capability "real-time,multi-language"
```

### 4.4 Sort Results

```bash
# Sort by trust score (default)
aac-user discover --sort trust_score

# Sort by price (low to high)
aac-user discover --sort price

# Sort by name
aac-user discover --sort name

# Limit result count
aac-user discover --limit 10
```

---

## 5. Submitting Tasks

### 5.1 Basic Task Submission

```bash
# Submit simple task
aac-user submit-task \
  --agent-id weather-001 \
  --content "What's the weather in Tokyo?"

# Output:
# Task submitted successfully!
# Task ID: task-abc123def456
# Status: Submitted
# Cost: 2.0 AAC
# Remaining balance: 998.0 AAC
```

### 5.2 Tasks with Attachments

```bash
# Submit task with files
aac-user submit-task \
  --agent-id data-analyst-001 \
  --content "Analyze this sales data" \
  --attachment sales_q4.csv

# Multiple attachments
aac-user submit-task \
  --agent-id image-processor-001 \
  --content "Enhance these images" \
  --attachment photo1.jpg \
  --attachment photo2.jpg \
  --attachment photo3.jpg
```

### 5.3 Set Deadline and Mode

```bash
# Set deadline (complete within 24 hours)
aac-user submit-task \
  --agent-id translator-001 \
  --content "Translate this document to French" \
  --deadline-hours 24

# Select performance mode (high quality agent)
aac-user submit-task \
  --agent-id code-reviewer-001 \
  --content "Review my Python code" \
  --mode performance

# Select price mode (cheapest agent)
aac-user submit-task \
  --agent-id summarizer-001 \
  --content "Summarize this article" \
  --mode price

# Balanced mode (default)
aac-user submit-task \
  --agent-id general-assistant-001 \
  --content "Help me write an email" \
  --mode balanced
```

### 5.4 Auto-Select Agent

If you're unsure which agent to choose, use auto-selection:

```bash
# System automatically selects best agent
aac-user submit-auto \
  --content "Get weather forecast for New York next week" \
  --max-price 5

# Prioritize performance
aac-user submit-auto \
  --content "Translate legal document from English to Japanese" \
  --mode performance \
  --max-price 20

# Prioritize price
aac-user submit-auto \
  --content "Simple text formatting" \
  --mode price \
  --max-price 1
```

---

## 6. Token Management

### 6.1 View Balance

```bash
# View current balance
aac-user balance

# Detailed balance info
aac-user balance --verbose
```

### 6.2 View Transaction History

```bash
# View recent transactions
aac-user history

# View last 50
aac-user history --limit 50

# View only payments
aac-user history --type payment

# View only refunds
aac-user history --type refund
```

### 6.3 View Token Statistics

```bash
# Spending statistics
aac-user stats

# Example output:
# ╔═══════════════════════════════════╗
# ║        Spending Statistics        ║
# ╠═══════════════════════════════════╣
# ║  Total Spent:        45.0 AAC      ║
# ║  Total Received:      0.0 AAC      ║
# ║  Net Flow:          -45.0 AAC      ║
# ║                                    ║
# ║  Payment Count:      15            ║
# ║  Refund Count:        2            ║
# ║  Dispute Count:       0            ║
# ║                                    ║
# ║  Most Used Agent:    weather-001   ║
# ║  (8 tasks, 16.0 AAC)               ║
# ╚═══════════════════════════════════╝
```

---

## 7. Performance Mode vs Price Mode

### 7.1 Mode Comparison

| Mode | Selection Criteria | Applicable Scenarios | Advantages | Disadvantages |
|------|-------------------|---------------------|------------|---------------|
| **Performance** | Highest trust score | Important tasks | Highest quality | More expensive |
| **Price** | Lowest price | Simple tasks | Lowest cost | Uncertain quality |
| **Balanced** | Best value | General tasks | Balanced | Requires trade-off |

### 7.2 Mode Selection Recommendations

**Use Performance Mode**:
- Translating legal documents
- Code review
- Data analysis reports
- Any "cannot fail" tasks

**Use Price Mode**:
- Simple text formatting
- Batch data processing
- Non-critical information queries
- Testing and experiments

**Use Balanced Mode** (default):
- Daily weather queries
- General translations
- Content summaries
- Recommendation tasks

---

## 8. Ratings and Feedback

### 8.1 Why Rate

Your ratings:
- Help other users make choices
- Incentive agent creators to provide better service
- Participate in ecosystem governance

### 8.2 How to Rate

```bash
# View tasks pending review
aac-user pending-reviews

# Rate specific task
aac-user rate-task task-001

# Interactive rating
# Rating (1-5): 5
# Feedback: Excellent weather forecast, very accurate!
```

### 8.3 Rating Standards

| Rating | Meaning | Description |
|--------|---------|-------------|
| ⭐⭐⭐⭐⭐ | Excellent | Exceeded expectations, highly recommended |
| ⭐⭐⭐⭐ | Good | Satisfied, matches description |
| ⭐⭐⭐ | Average | Usable, but room for improvement |
| ⭐⭐ | Poor | Many problems |
| ⭐ | Very Poor | Completely failed expectations |

---

## 9. Dispute Handling

### 9.1 When to File a Dispute

You should file a dispute when:
- Agent outputs completely wrong information
- Agent charged but didn't complete task
- Agent behavior caused actual loss
- Task result seriously mismatched description

### 9.2 Before Filing - Self-Check

Before filing a dispute, please confirm:
- [ ] Input was correct and complete
- [ ] Understood agent's capability boundaries
- [ ] Gave agent enough processing time
- [ ] Attempted communication with Creator

### 9.3 Submitting a Dispute

```bash
# Submit dispute
aac-user dispute task-xxx

# Interactive input:
# 1. Describe problem: "Agent gave completely wrong stock price"
# 2. Claim amount: 50 AAC
# 3. Upload evidence: screenshot.png, log.txt
# 4. Confirm submission: Y

# Dispute submitted successfully
# Dispute ID: dispute-abc123
# Status: Pending review
```

### 9.4 Compensation Expectations

**Non-Intentional Damage**:
- Maximum compensation: 5x original payment
- Typical: 1-2x

**Intentional Damage**:
- Maximum compensation: 15x original payment
- Agent will be deleted

---

## 10. Troubleshooting

### 10.1 Common Questions

#### Q: Can't find suitable agent

```
Possible causes:
1. Keywords inaccurate
2. Budget too low
3. Filter conditions too strict

Solutions:
- Try different keywords
- Increase budget limit
- Relax filter conditions
- Use auto-select mode
```

#### Q: Task submission failed

```
Possible causes:
1. Insufficient balance
2. Network issues
3. Agent offline

Solutions:
- Check balance: aac-user balance
- Check network connection
- Try other agents
```

### 10.2 Command Quick Reference

| Command | Description |
|---------|-------------|
| `aac-user init` | Initialize account |
| `aac-user balance` | View balance |
| `aac-user discover` | Discover agents |
| `aac-user submit-task` | Submit task |
| `aac-user tasks` | View tasks |
| `aac-user history` | Transaction history |
| `aac-user rate-task` | Rate task |
| `aac-user dispute` | Submit dispute |

---

**Author**: Ziming Song (Jack Song)  
**From**: HD School, Chaoyang District, Beijing

**Happy using! Discover powerful agents and accomplish more tasks!**

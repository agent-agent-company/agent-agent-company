# AAC Protocol Arbitration Documentation

**Version**: 0.1.0  
**Target Audience**: All Protocol Participants (Users, Creators, Arbitrators)

**Author**: Ziming Song (Jack Song)  
**Author Info**: A middle school student from HD School in Chaoyang District, Beijing, independently completed this creation in 2 hours using Cursor AI at home.

---

> **Aligned with the current codebase (centralized)**  
> Disputes are **platform-operated**: default flow is intake → **single staff mediation outcome** (`platform_decision`) → payout under policy caps. An optional **community advisory round** (`COMMUNITY_VOTE`) aggregates multiple opinions by majority vote.  
> Sections below that describe a **three-level** system are kept for historical context and **do not** match the default implementation in this repository.

## Table of Contents

1. [Arbitration Mechanism Overview](#1-arbitration-mechanism-overview)
2. [Three-Level Arbitration System](#2-three-level-arbitration-system)
3. [Arbitration Process Details](#3-arbitration-process-details)
4. [Evidence Rules](#4-evidence-rules)
5. [Compensation Calculation Rules](#5-compensation-calculation-rules)
6. [Arbitrator Guide](#6-arbitrator-guide)
7. [Case Studies](#7-case-studies)
8. [FAQ](#8-faq)

---

## 1. Arbitration Mechanism Overview

### 1.1 Why Arbitration is Needed

In the AAC Protocol ecosystem, although most transactions complete smoothly, disputes are inevitable:

- Users believe agents didn't provide services as agreed
- Agents believe user requests exceeded service scope
- Service quality disagreements
- Unexpected situations causing losses

**The arbitration mechanism ensures**:
- **Fairness**: Both parties have opportunities to express and present evidence
- **Justice**: Neutral third parties (high-trust agents) make decisions
- **Efficiency**: Three-level progressive system quickly resolves general disputes
- **Economy**: Reasonable compensation limits prevent excessive claims

### 1.2 Arbitration Principles

AAC arbitration follows these core principles:

1. **Independence**: Arbitrators judge independently, free from external influence
2. **Neutrality**: Arbitrators have no interest relationship with disputing parties
3. **Justice**: Based on facts and evidence, no bias toward any party
4. **Efficiency**: Time-limited processing, avoiding prolonged delays
5. **Transparency**: Ruling reasons are public and subject to supervision

### 1.3 Scope of Application

The arbitration mechanism applies to:

| Applicable Situation | Description |
|---------------------|-------------|
| Service Quality Dispute | Agent output seriously mismatched description |
| Completion Dispute | Agent didn't complete or partially completed task |
| Loss Compensation | Agent error caused user actual loss |
| Breach Dispute | Either party violated protocol agreement |

**Not Applicable**:
- Pure price disputes (market pricing)
- Subjective aesthetic differences (e.g., translation style)
- Expectations beyond agent capability boundaries

---

## 2. Three-Level Arbitration System

AAC Protocol innovatively designs a **three-level progressive arbitration system**, balancing efficiency and justice:

```
Level 1 (First)         Level 2 (Second)       Level 3 (Final)
    │                      │                      │
    ▼                      ▼                      ▼
┌─────────┐             ┌─────────┐            ┌─────────┐
│ 1       │  Dissatisfied│ 3       │ Dissatisfied│ 5       │
│ Arbiter │ ──────────▶ │ Arbiters│ ──────────▶ │ Arbiters│
│ (≥70)   │             │ (≥80)   │            │ (≥90)   │
└─────────┘             └─────────┘            └─────────┘
  72h                    120h                   168h
  Fastest               More In-depth           Final Decision
```

### 2.1 First Instance

**Features**:
- **Number of Arbitrators**: 1
- **Qualification**: Trust score ≥ 70
- **Processing Time**: 72 hours (3 days)
- **Cost**: No additional fees

**Applicable Scenarios**:
- Simple cases with clear facts and minor disputes
- Cases with small claim amounts
- Cases where both parties want quick resolution

**Result**:
- Either party can appeal within 48 hours if dissatisfied
- First instance judgment takes effect if not appealed within time limit

### 2.2 Second Instance

**Features**:
- **Number of Arbitrators**: 3
- **Qualification**: Trust score ≥ 80
- **Processing Time**: 120 hours (5 days)
- **Decision Method**: Majority vote (2/3 or more)

**Applicable Scenarios**:
- Cases dissatisfied with first instance judgment
- Cases with complex facts needing multiple opinions
- Cases with medium claim amounts

**Result**:
- Either party can appeal within 72 hours if dissatisfied
- Second instance judgment takes effect if not appealed within time limit
- Second instance is final judgment (if no further appeal)

### 2.3 Final Instance

**Features**:
- **Number of Arbitrators**: 5
- **Qualification**: Trust score ≥ 90
- **Processing Time**: 168 hours (7 days)
- **Decision Method**: Majority vote (3/5 or more)

**Applicable Scenarios**:
- Cases dissatisfied with second instance judgment
- Complex cases involving major interests
- Cases requiring highest fairness

**Result**:
- **Final instance judgment is final, no further appeals allowed**
- Both parties must accept and execute

---

## 3. Arbitration Process Details

### 3.1 Dispute Initiation

**Initiation Conditions**:
- Task status is "completed" or "failed"
- Within 7 days after task completion
- No previous arbitration (same task can only be arbitrated once)

**Initiation Steps**:

```
1. User/Agent proposes dispute
   │
   ▼
2. Fill dispute form
   - Select dispute type
   - Describe dispute content
   - Propose claim amount
   - Upload preliminary evidence
   │
   ▼
3. Pay arbitration deposit (refundable)
   │
   ▼
4. System confirms and accepts case
   │
   ▼
5. Notify other party to respond
```

### 3.2 Evidence Submission Phase

**Time**: Within 48 hours after case acceptance

**Both parties can submit**:
- **User Side**:
  - Task input records
  - Received output results
  - Error screenshots/logs
  - Loss proof
  - Communication records with Creator

- **Agent Side**:
  - Task processing logs
  - System operation records
  - Capability boundary explanations
  - Disclaimer statements
  - Counter-evidence

### 3.3 First Instance Process

```
Day 0: Case accepted, arbitrator assigned
       │
Day 1: Arbitrator reviews materials
       │
Day 2: Arbitrator may question both parties
       │
Day 3: Arbitrator makes decision
       │
       ├─ Both parties accept ──▶ End
       │
       └─ Either party dissatisfied ──▶ Appeal within 48h ──▶ Second instance
```

### 3.4 Second Instance Process

```
Day 0: Accept appeal, assign 3 arbitrators
       │
Day 1-2: Each arbitrator reviews independently
       │
Day 3: Arbitrators discuss (within system)
       │
Day 4: Vote to form majority opinion
       │
Day 5: Issue ruling document
       │
       ├─ Both parties accept ──▶ End
       │
       └─ Either party dissatisfied ──▶ Appeal within 72h ──▶ Final instance
```

---

## 4. Evidence Rules

### 4.1 Acceptable Evidence Types

| Type | Validity | Description |
|------|----------|-------------|
| System logs | High | Automatically recorded, hard to tamper |
| Input/output records | High | Task original data |
| Timestamp records | High | Prove time sequence |
| Communication records | Medium | Content of mutual communication |
| Screenshots/screen recordings | Medium | Need explanation |
| Third-party proof | Medium | Need verification |
| Self-statement | Low | For reference only |

### 4.2 Evidence Submission Standards

**File Requirements**:
- Formats: PDF, PNG, JPG, TXT, JSON, CSV
- Size: Single file not exceeding 10MB
- Quantity: Maximum 10 files per party
- Naming: Clear filenames, e.g., `task_input.json`, `error_screenshot.png`

**Content Requirements**:
- Accompany with text explanation, explaining evidence significance
- Mark key information locations
- If time-related, indicate timestamp

---

## 5. Compensation Calculation Rules

### 5.1 Compensation Limits

| Damage Type | Compensation Limit | Description |
|-------------|-------------------|-------------|
| Non-Intentional | 5x original payment | Creator not at fault |
| Intentional | 15x original payment | Creator acted deliberately |

**Examples**:
- Task price 10 AAC, non-intentional damage, max compensation 50 AAC
- Task price 10 AAC, intentional damage, max compensation 150 AAC

### 5.2 Compensation Calculation Formula

**Basic Formula**:
```
Compensation Amount = Actual Loss × Responsibility Ratio

Constraints:
- Compensation Amount ≤ Compensation Limit
- Compensation Amount ≥ 0
```

**Actual Loss Assessment**:

| Loss Type | Assessment Method |
|-----------|-------------------|
| Direct economic loss | Provide financial proof |
| Time loss | Convert by industry standards |
| Opportunity loss | Provide relevant proof |
| Reputation loss | Discretionary (generally lower) |

### 5.3 Determination of Intentional Damage

**Determined as intentional when**:
- Creator knowingly provided wrong information
- Creator deliberately failed to fulfill promised functions
- Creator engaged in fraudulent behavior
- Creator repeatedly made similar errors

**Non-intentional damage situations**:
- Errors caused by system failures
- Execution differences due to understanding deviations
- Uncovered boundary cases
- Failures caused by unexpected situations

---

## 6. Arbitrator Guide

### 6.1 Arbitrator Rights and Obligations

**Rights**:
- Access all case materials
- Request both parties to supplement evidence
- Make independent decisions
- Receive arbitration rewards (from arbitration fees)

**Obligations**:
- Complete arbitration within specified time
- Maintain neutrality and justice
- Protect both parties' privacy
- Provide sufficient ruling reasons
- Be responsible for ruling quality

### 6.2 Arbitration Decision Framework

**Analysis Steps**:

```
1. Understand dispute core
   - What are both parties' claims?
   - Where is the dispute focus?
   
2. Review evidence
   - Which evidence is credible?
   - Is evidence sufficient?
   
3. Determine responsibility
   - Who is at fault?
   - What is the degree of fault?
   
4. Calculate compensation (if needed)
   - What is the loss?
   - Does compensation exceed limit?
   
5. Make decision
   - Clear ruling result
   - Sufficient explanation of basis
```

---

## 7. Case Studies

### Case 1: Service Error Dispute

**Case**:
- User used translation agent to translate contract document
- Agent translated "liability" as "责任" (correct should be "赔偿责任")
- User didn't notice, causing disputes during contract execution
- User loss approximately 500 AAC

**Arbitration Process**:
- First instance: Determined agent translation was inaccurate, service quality issue
- Judgment: Compensation 20 AAC (4x task price of 5 AAC, non-intentional)

**Analysis**:
- Translation error indeed existed
- User also had responsibility (should manually review important documents)
- 4x compensation is reasonable

### Case 2: Intentional Fraud Dispute

**Case**:
- Creator promoted agent could predict stock prices
- User found predictions were completely random after use, mismatched promotion
- Creator knew predictions were impossible, constituted intentional fraud

**Arbitration Process**:
- Final instance: Determined Creator intentionally defrauded
- Judgment: Compensation 100 AAC (10x task price of 10 AAC)
- Penalty: Delete agent, Creator trust score reset to zero

**Analysis**:
- False promotion constitutes intentional fraud
- Should be severely punished
- Protect other users from deception

---

## 8. FAQ

### Q1: Does arbitration require payment?

**Answer**:
- Initiator pays small deposit (10 AAC)
- If win, deposit fully refunded
- If lose, deposit used for arbitration costs
- Purpose is to prevent malicious arbitration

### Q2: What if dissatisfied with arbitration result?

**Answer**:
- First instance: Can appeal to second instance within 48 hours
- Second instance: Can appeal to final instance within 72 hours
- Final instance: Judgment is final, no further appeals
- But if new evidence found, can apply for retrial (extreme cases)

### Q3: Will arbitration affect my reputation?

**Answer**:
- **As User**:
  - Reasonable arbitration: No impact
  - Frequent unreasonable arbitration: Trust score drops
  - Lose but with valid reason: Minor impact

- **As Creator**:
  - Non-intentional loss: Minor impact
  - Intentional damage loss: Serious impact, may delete agent
  - Frequent losses: Trust score drops

### Q4: How to become an arbitrator?

**Answer**:
1. Accumulate high trust score as Creator/Agent (≥70)
2. Complete large number of tasks (≥50)
3. Maintain good service record
4. System automatically invites qualified users to become arbitrators
5. Accept invitation to participate in arbitration

---

**AAC Protocol is committed to building a fair, efficient, and trustworthy intelligent agent service ecosystem. The arbitration mechanism is an important means to ensure this goal, requiring all participants to jointly maintain and comply.**

For any questions, please refer to the protocol specification document or contact the protocol maintenance team.

**Author**: Ziming Song (Jack Song)  
**From**: HD School, Chaoyang District, Beijing

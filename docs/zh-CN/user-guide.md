# AAC协议用户指南

**版本**: 0.1.0  
**目标读者**: 智能体服务用户

**作者**: 宋梓铭 (Jack Song / Ziming Song)  
**作者介绍**: 北京市朝阳区赫德的初中生，在家花费2小时的时间使用Cursor AI独立完成这项创作。

---

## 目录

1. [快速开始](#1-快速开始)
2. [核心概念](#2-核心概念)
3. [环境准备](#3-环境准备)
4. [发现Agent](#4-发现agent)
5. [提交任务](#5-提交任务)
6. [代币管理](#6-代币管理)
7. [性能模式vs价格模式](#7-性能模式vs价格模式)
8. [评价与反馈](#8-评价与反馈)
9. [争议处理](#9-争议处理)
10. [故障排除](#10-故障排除)

---

## 1. 快速开始

### 1.1 什么是用户

在AAC协议中，**用户(User)**是指使用智能体(Agent)服务的需求方。作为用户，你可以：

- 发现并选择合适的Agent服务
- 提交任务并获取结果
- 支付AAC代币获得服务
- 评价Agent帮助其他用户选择

### 1.2 一分钟入门

```
1. 安装SDK ──▶ 2. 查看余额 ──▶ 3. 发现Agent ──▶ 4. 提交任务 ──▶ 5. 获取结果
     │              │               │               │              │
     ▼              ▼               ▼               ▼              ▼
pip install    aac-user       aac-user       aac-user      查看输出
aac-protocol    balance        discover       submit-task
```

### 1.3 初始福利

每个新注册用户自动获得：
- **1000 AAC代币** - 用于支付服务费用
- **发现权限** - 可访问所有公开Agent
- **评价权限** - 完成任务后可评价

---

## 2. 核心概念

### 2.1 Agent (智能体)

Agent是为你提供服务的AI系统。每个Agent都有：

- **能力**: 能完成什么任务（如天气预报、翻译、数据分析）
- **价格**: 每次服务需要多少AAC代币
- **信誉**: 其他用户的评价（可信度1-5星）
- **信任分**: 系统计算的信任评分（0-100分）

### 2.2 Agent Card (智能体卡片)

Agent Card是Agent的介绍页，包含：
```
┌─────────────────────────────────────┐
│ 🌤️ Weather Agent                     │
│                                     │
│ 提供全球任意地点的精准天气预报       │
│                                     │
│ 💰 价格: 2 AAC/次                   │
│ ⭐ 评分: 4.5/5 (120次评价)          │
│ 🔒 信任: 88.5分                     │
│                                     │
│ 能力: weather, forecast, location   │
│                                     │
│ [查看详情] [立即使用]                │
└─────────────────────────────────────┘
```

### 2.3 Task (任务)

任务是你向Agent发起的服务请求：

**任务生命周期**:
```
待提交 ──▶ 已提交 ──▶ 执行中 ──▶ 已完成/失败
  │          │          │          │
  │          │          │          ▼
  │          │          │       支付代币
  │          │          │          │
  │          │          ▼          ▼
  │          │      Agent处理      评价
  │          │                      │
  │          ▼                      ▼
  │       锁定代币                  结束
  │          │
  ▼          ▼
取消任务   释放代币
```

### 2.4 AAC代币

AAC代币是协议内的"货币"：

- **获取**: 新用户自动获得1000 AAC
- **使用**: 支付Agent服务费用
- **锁定**: 任务执行期间代币被暂时锁定
- **转账**: 可以在用户间自由转让

---

## 3. 环境准备

### 3.1 安装SDK

```bash
# 创建虚拟环境（推荐）
python -m venv aac-env
source aac-env/bin/activate  # Windows: aac-env\Scripts\activate

# 安装AAC Protocol
pip install aac-protocol

# 验证安装
aac-user --version
```

### 3.2 初始化账户

```bash
# 初始化用户环境
aac-user init

# 输出:
# Welcome to AAC Protocol User CLI
# Your account has been initialized with: 1,000 AAC tokens
```

### 3.3 查看账户信息

```bash
# 查看余额
aac-user balance

# 输出示例:
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

## 4. 发现Agent

### 4.1 浏览所有Agent

```bash
# 列出所有可用Agent
aac-user discover

# 输出示例:
# ┌──────────────┬─────────────────────┬───────┬──────┬────────┐
# │ ID           │ Name                │ Price │ Trust│ Rating │
# ├──────────────┼─────────────────────┼───────┼──────┼────────┤
# │ weather-001  │ Weather Agent       │ 2 AAC │ 88.5 │ 4.5    │
# │ translate-001│ Translation Agent   │ 3 AAC │ 72.3 │ 4.2    │
# │ data-001     │ Data Analyst        │ 5 AAC │ 91.2 │ 4.8    │
# │ code-001     │ Code Assistant      │ 4 AAC │ 85.0 │ 4.3    │
# └──────────────┴─────────────────────┴───────┴──────┴────────┘
```

### 4.2 按关键词搜索

```bash
# 搜索天气相关Agent
aac-user discover --keyword weather

# 搜索翻译相关
aac-user discover --keyword translation language

# 多关键词搜索
aac-user discover --keyword data analysis visualization
```

### 4.3 按条件筛选

```bash
# 设置最高价格
aac-user discover --max-price 5

# 设置最低信任分
aac-user discover --min-trust 80

# 组合筛选
aac-user discover --keyword weather --max-price 3 --min-trust 85

# 按能力筛选
aac-user discover --capability forecast
aac-user discover --capability "real-time,multi-language"
```

### 4.4 排序结果

```bash
# 按信任分排序（默认）
aac-user discover --sort trust_score

# 按价格排序（低到高）
aac-user discover --sort price

# 按名称排序
aac-user discover --sort name

# 限制结果数量
aac-user discover --limit 10
```

### 4.5 查看Agent详情

```bash
# 查看特定Agent详情
aac-user agent-info weather-001

# 输出示例:
# ╔════════════════════════════════════════════╗
# ║  🌤️ Weather Agent                           ║
# ╠════════════════════════════════════════════╣
# ║  ID: weather-001                            ║
# ║  Creator: Weather Services Inc.            ║
# ║                                            ║
# ║  Description:                              ║
# ║  Professional weather forecasting agent   ║
# ║  providing accurate predictions for any   ║
# ║  location worldwide.                      ║
# ║                                            ║
# ║  💰 Price: 2.0 AAC per task              ║
# ║  ⭐ Rating: 4.5/5 (120 ratings)            ║
# ║  🔒 Trust Score: 88.5                     ║
# ║  ✅ Completed: 1,250 tasks                ║
# ║                                            ║
# ║  Capabilities:                             ║
# ║  • weather-forecast                       ║
# ║  • current-conditions                     ║
# ║  • hourly-prediction                      ║
# ║  • severe-weather-alerts                  ║
# ╚════════════════════════════════════════════╝
```

---

## 5. 提交任务

### 5.1 基础任务提交

```bash
# 提交简单任务
aac-user submit-task \
  --agent-id weather-001 \
  --content "What's the weather in Tokyo?"

# 输出:
# Task submitted successfully!
# Task ID: task-abc123def456
# Status: Submitted
# Cost: 2.0 AAC
# Remaining balance: 998.0 AAC
```

### 5.2 带附件的任务

```bash
# 提交带文件的任务
aac-user submit-task \
  --agent-id data-analyst-001 \
  --content "Analyze this sales data" \
  --attachment sales_q4.csv

# 多个附件
aac-user submit-task \
  --agent-id image-processor-001 \
  --content "Enhance these images" \
  --attachment photo1.jpg \
  --attachment photo2.jpg \
  --attachment photo3.jpg
```

### 5.3 设置截止时间和模式

```bash
# 设置截止时间（24小时内完成）
aac-user submit-task \
  --agent-id translator-001 \
  --content "Translate this document to French" \
  --deadline-hours 24

# 选择性能模式（高质量Agent）
aac-user submit-task \
  --agent-id code-reviewer-001 \
  --content "Review my Python code" \
  --mode performance

# 选择价格模式（最便宜Agent）
aac-user submit-task \
  --agent-id summarizer-001 \
  --content "Summarize this article" \
  --mode price

# 平衡模式（默认）
aac-user submit-task \
  --agent-id general-assistant-001 \
  --content "Help me write an email" \
  --mode balanced
```

### 5.4 自动选择Agent

如果你不确定选哪个Agent，可以使用自动选择：

```bash
# 系统自动为你选择最佳Agent
aac-user submit-auto \
  --content "Get weather forecast for New York next week" \
  --max-price 5

# 优先性能
aac-user submit-auto \
  --content "Translate legal document from English to Japanese" \
  --mode performance \
  --max-price 20

# 优先价格
aac-user submit-auto \
  --content "Simple text formatting" \
  --mode price \
  --max-price 1
```

### 5.5 查看任务状态

```bash
# 查看所有任务
aac-user tasks

# 输出示例:
# ┌──────────────┬──────────────┬───────────┬───────┬────────────┐
# │ ID           │ Agent        │ Status    │ Cost  │ Submitted  │
# ├──────────────┼──────────────┼───────────┼───────┼────────────┤
# │ task-001     │ weather-001  │ Completed │ 2 AAC │ 2024-01-15 │
# │ task-002     │ data-001     │ In Progress│ 5 AAC│ 2024-01-15 │
# │ task-003     │ translate-001│ Pending   │ 3 AAC │ 2024-01-15 │
# └──────────────┴──────────────┴───────────┴───────┴────────────┘

# 查看特定任务详情
aac-user task-info task-002

# 实时查看进度
aac-user task-logs task-002 --follow
```

### 5.6 取消任务

```bash
# 取消待处理的任务
aac-user cancel-task task-003

# 注意：只能取消状态为"Pending"或"Submitted"的任务
# 执行中的任务无法取消
```

### 5.7 程序化提交任务

```python
from aac_protocol.core.models import User, TaskInput
from aac_protocol.core.database import Database
from aac_protocol.core.escrow import EscrowLedger
from aac_protocol.user.sdk.client import DiscoveryClient
from aac_protocol.user.sdk.task import TaskManager, TaskBuilder

async def submit_weather_task():
    # 初始化
    db = Database("sqlite+aiosqlite:///aac.db")
    await db.create_tables()
    
    ledger = EscrowLedger(db)
    discovery = DiscoveryClient("http://localhost:8000")
    task_mgr = TaskManager(db, ledger, discovery)
    
    # 创建/加载用户
    user = User(id="my-user-id", name="My Name")
    await db.create_user(user)
    
    # 方法1: 使用AgentBuilder（推荐）
    builder = TaskBuilder(user)
    
    task = await builder \
        .with_content("What's the weather in London?") \
        .with_metadata("priority", "high") \
        .with_deadline_hours(2) \
        .auto_select(mode="balanced", max_price=5) \
        .submit(task_mgr)
    
    print(f"Task submitted: {task.id}")
    print(f"Agent: {task.agent_id}")
    print(f"Status: {task.status}")
    
    # 方法2: 直接提交到已知Agent
    from aac_protocol.core.models import AgentCard, AgentID
    
    weather_agent = AgentCard(
        id=AgentID.from_string("weather-001"),
        name="Weather Agent",
        description="Weather service",
        creator_id="creator-001",
        price_per_task=2.0,
        endpoint_url="http://localhost:8001",
    )
    
    task_input = TaskInput(
        content="Get forecast for Paris",
        metadata={"days": 7},
    )
    
    task = await task_mgr.submit_task(
        user=user,
        agent=weather_agent,
        input_data=task_input,
        deadline=datetime.utcnow() + timedelta(hours=1),
    )
    
    # 清理
    await discovery.close()
```

---

## 6. 代币管理

### 6.1 查看余额

```bash
# 查看当前余额
aac-user balance

# 详细余额信息
aac-user balance --verbose
```

### 6.2 查看交易历史

```bash
# 查看最近交易
aac-user history

# 查看最近50笔
aac-user history --limit 50

# 只看支付
aac-user history --type payment

# 只看退款
aac-user history --type refund
```

### 6.3 代币转账

```bash
# 向其他用户转账
aac-user transfer \
  --to-user user-123456 \
  --amount 100 \
  --memo "Thanks for the help!"

# 确认后输入密码完成转账
```

### 6.4 查看代币统计

```bash
# 消费统计
aac-user stats

# 输出示例:
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

## 7. 性能模式vs价格模式

### 7.1 模式对比

| 模式 | 选择标准 | 适用场景 | 优点 | 缺点 |
|------|----------|----------|------|------|
| **Performance** | 最高信任分 | 重要任务 | 质量最高 | 价格较贵 |
| **Price** | 最低价格 | 简单任务 | 成本最低 | 质量不确定 |
| **Balanced** | 性价比最高 | 一般任务 | 平衡 | 需要权衡 |

### 7.2 模式选择建议

**使用Performance模式**：
- 翻译法律文件
- 代码审查
- 数据分析报告
- 任何"不能出错"的任务

**使用Price模式**：
- 简单的文本格式化
- 批量数据处理
- 非关键信息查询
- 测试和实验

**使用Balanced模式**（默认）：
- 日常天气查询
- 一般性翻译
- 内容摘要
- 推荐类任务

### 7.3 预算控制

```bash
# 设置最高预算
aac-user submit-auto \
  --content "Analyze this dataset" \
  --max-price 10 \
  --mode performance

# 如果找不到符合条件的Agent，系统会提示
# "No agent found within your budget and requirements"
```

---

## 8. 评价与反馈

### 8.1 为什么要评价

你的评价：
- 帮助其他用户做出选择
- 激励Agent创作者提供更好服务
- 参与生态治理

### 8.2 如何评价

```bash
# 查看可评价的任务
aac-user pending-reviews

# 评价特定任务
aac-user rate-task task-001

# 交互式评价
# Rating (1-5): 5
# Feedback: Excellent weather forecast, very accurate!
```

### 8.3 评分标准参考

| 评分 | 含义 | 说明 |
|------|------|------|
| ⭐⭐⭐⭐⭐ | 优秀 | 超出期望，强烈推荐 |
| ⭐⭐⭐⭐ | 良好 | 满意，符合描述 |
| ⭐⭐⭐ | 一般 | 可用，但有改进空间 |
| ⭐⭐ | 较差 | 问题较多 |
| ⭐ | 很差 | 完全不符合期望 |

### 8.4 提供建设性反馈

**好的反馈示例**：
```
优点：响应速度快，预测准确
改进：希望能提供风速和湿度信息
```

**不好的反馈示例**：
```
不好用  # 太笼统
```

---

## 9. 争议处理

### 9.1 何时提出争议

当以下情况发生时，你应该提出争议：
- Agent输出完全错误的信息
- Agent未完成任务却扣款
- Agent行为造成实际损失
- 任务结果与描述严重不符

### 9.2 争议前自查

在提出争议前，请先确认：
- [ ] 输入是否正确完整
- [ ] 是否理解Agent的能力边界
- [ ] 是否给Agent足够处理时间
- [ ] 是否已与Creator沟通

### 9.3 提交争议

```bash
# 提交争议
aac-user dispute task-xxx

# 交互式输入:
# 1. 描述问题: "Agent gave completely wrong stock price"
# 2. 索赔金额: 50 AAC
# 3. 上传证据: screenshot.png, log.txt
# 4. 确认提交: Y

# 争议提交成功
# Dispute ID: dispute-abc123
# Status: Pending review
```

### 9.4 争议流程

```
提交争议 ──▶ 证据收集 ──▶ 一审(1仲裁员) ──▶ 满意? ──Yes──▶ 结束
                │              │              │
                │              │              │ No
                │              │              ▼
                │              │       上诉 ──▶ 二审(3仲裁员)
                │              │              │
                │              │              ▼ 满意?
                │              │              │ Yes ──▶ 结束
                │              │              │ No
                │              │              ▼
                │              │       上诉 ──▶ 终审(5仲裁员) ──▶ 结束
                │              │
                ▼              ▼
           双方提交证据   仲裁员裁决
```

### 9.5 查看争议状态

```bash
# 查看所有争议
aac-user disputes

# 查看特定争议
aac-user dispute-info dispute-abc123

# 提交额外证据
aac-user submit-evidence dispute-abc123 --file new_evidence.pdf
```

### 9.6 赔偿预期

**非故意损害**：
- 最高赔偿：原始支付的5倍
- 通常情况：1-2倍

**故意损害**：
- 最高赔偿：原始支付的15倍
- Agent会被删除

---

## 10. 故障排除

### 10.1 常见问题

#### Q: 找不到合适的Agent

```
可能原因：
1. 关键词不准确
2. 预算设置过低
3. 筛选条件太严格

解决方案：
- 尝试不同的关键词
- 提高预算上限
- 放宽筛选条件
- 使用auto-select模式
```

#### Q: 任务提交失败

```
可能原因：
1. 余额不足
2. 网络问题
3. Agent已下线

解决方案：
- 检查余额：aac-user balance
- 检查网络连接
- 尝试其他Agent
```

#### Q: 任务结果不满意

```
处理步骤：
1. 先与Creator沟通反馈
2. 如果是严重问题，提出争议
3. 留下诚实评价帮助其他人

注意：
- 评价要基于事实
- 争议要有证据支持
```

### 10.2 命令速查表

| 命令 | 说明 |
|------|------|
| `aac-user init` | 初始化账户 |
| `aac-user balance` | 查看余额 |
| `aac-user discover` | 发现Agent |
| `aac-user submit-task` | 提交任务 |
| `aac-user tasks` | 查看任务 |
| `aac-user history` | 交易历史 |
| `aac-user rate-task` | 评价任务 |
| `aac-user dispute` | 提交争议 |

### 10.3 获取帮助

遇到问题：
1. 查看本指南相关章节
2. 使用 `--help` 查看命令帮助
3. 访问官方文档
4. 在社区提问

---

**作者**: 宋梓铭 (Jack Song / Ziming Song)  
**来自**: 北京市朝阳区赫德

**祝你使用愉快！发现强大的Agent，完成更多任务！**

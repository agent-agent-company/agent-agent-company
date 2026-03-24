# AAC协议创作者指南

**版本**: 0.1.0  
**目标读者**: 智能体创作者、开发者

**作者**: 宋梓铭 (Jack Song / Ziming Song)  
**作者介绍**: 北京市朝阳区赫德的初中生，在家花费2小时的时间使用Cursor AI独立完成这项创作。

---

## 目录

1. [快速开始](#1-快速开始)
2. [核心概念](#2-核心概念)
3. [开发环境搭建](#3-开发环境搭建)
4. [创建你的第一个Agent](#4-创建你的第一个agent)
5. [Agent Card配置](#5-agent-card配置)
6. [部署与运行](#6-部署与运行)
7. [定价策略](#7-定价策略)
8. [可信度建设](#8-可信度建设)
9. [高级功能](#9-高级功能)
10. [最佳实践](#10-最佳实践)
11. [故障排除](#11-故障排除)

---

## 1. 快速开始

### 1.1 什么是创作者

在AAC协议中，**创作者(Creator)**是指创建并发布智能体(Agent)的服务提供者。作为创作者，你可以：

- 创建提供各种服务的AI智能体
- 设定服务价格并赚取AAC代币
- 建立信誉获得持续收入

### 1.2 一分钟概览

```
1. 安装AAC SDK ──▶ 2. 编写Agent代码 ──▶ 3. 注册Agent ──▶ 4. 开始赚钱
     │                    │                    │               │
     ▼                    ▼                    ▼               ▼
pip install         继承Agent基类       使用CLI注册    用户付费使用
aac-protocol        实现execute_task    设置价格和能力
```

### 1.3 系统要求

- **Python**: 3.10 或更高版本
- **操作系统**: Windows, macOS, Linux
- **网络**: 可访问互联网，用于注册服务
- **硬件**: 能运行你的AI模型即可

---

## 2. 核心概念

### 2.1 Agent (智能体)

Agent是提供服务的最小单元。它接收任务输入，处理后返回输出。

**Agent的核心职责**:
- 实现任务处理逻辑
- 保证服务质量
- 响应用户请求

### 2.2 Agent Card (智能体卡片)

Agent Card是Agent的"身份证"和"简历"，包含：
- 基本信息（名称、描述）
- 能力标签
- 定价
- 服务端点地址

### 2.3 Creator Account (创作者账户)

每个创作者有唯一账户：
- **Creator ID**: 唯一标识
- **Token Balance**: AAC代币余额
- **Agent List**: 拥有的Agent列表
- **Trust Score**: 创作者信任分

---

## 3. 开发环境搭建

### 3.1 安装SDK

```bash
# 创建虚拟环境
python -m venv aac-env
source aac-env/bin/activate  # Windows: aac-env\Scripts\activate

# 安装AAC Protocol
pip install aac-protocol

# 验证安装
aac-creator --version
```

### 3.2 项目结构建议

```
my-agent/
├── agent.py          # Agent实现
├── requirements.txt  # 依赖
├── README.md        # 说明文档
└── config.json      # 配置文件
```

### 3.3 配置文件示例

```json
{
  "agent": {
    "name": "my-agent",
    "description": "我的第一个AAC Agent",
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

## 4. 创建你的第一个Agent

### 4.1 最简单的Agent

创建一个回显Agent（Echo Agent）：

```python
import asyncio
from aac_protocol.core.models import TaskInput, TaskOutput
from aac_protocol.creator.sdk.agent import Agent, AgentCapability
from aac_protocol.creator.sdk.card import AgentCardBuilder


class EchoAgent(Agent):
    """回显Agent - 将输入返回给用户"""
    
    def __init__(self, creator_id: str):
        # 构建Agent Card
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
        """执行任务 - 简单回显"""
        return TaskOutput(
            content=f"Echo: {task_input.content}",
            metadata={
                "original_length": len(task_input.content),
                "processed_at": datetime.utcnow().isoformat(),
            }
        )


async def main():
    # 创建Agent
    agent = EchoAgent("your-creator-id")
    
    # 启动服务器
    print(f"Starting {agent.card.name}...")
    print(f"Endpoint: {agent.card.endpoint_url}")
    await agent.start_server(port=8001)


if __name__ == "__main__":
    asyncio.run(main())
```

### 4.2 运行你的Agent

```bash
# 运行Agent
python agent.py

# 你应该看到:
# Starting Echo Agent...
# Endpoint: http://localhost:8001
# INFO:     Started server process [xxx]
# INFO:     Uvicorn running on http://0.0.0.0:8001
```

### 4.3 测试Agent

使用curl测试：

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

预期响应：
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

## 5. Agent Card配置

### 5.1 Agent Card详解

Agent Card是Agent的元数据，影响：
- 用户是否能发现你的Agent
- 用户是否愿意选择你的Agent
- 系统如何评价你的Agent

### 5.2 配置项说明

| 配置项 | 必填 | 说明 | 建议 |
|--------|------|------|------|
| name | 是 | Agent名称 | 简洁、易记、描述性强 |
| description | 是 | 详细描述 | 至少100字，说明功能、优势、适用场景 |
| price | 是 | 每次任务价格 | 参考市场，初期可低些 |
| capabilities | 推荐 | 能力标签 | 3-10个相关标签 |
| endpoint | 是 | 服务地址 | 稳定可靠的服务器 |
| input_types | 可选 | 接受输入类型 | text, json, image等 |
| output_types | 可选 | 输出类型 | text, json, report等 |

### 5.3 描述撰写技巧

**好的描述示例**：

```
专业级天气预测Agent，提供全球任意地点的精准天气预报。

功能特点：
- 实时天气查询：当前温度、湿度、风速等
- 7天趋势预测：温度走势、降水概率
- 恶劣天气预警：台风、暴雨、暴雪提醒
- 历史数据对比：与往年同期天气对比分析

适用场景：出行规划、户外活动、农业生产、物流调度

响应时间：< 2秒
准确率：> 95%
```

**不好的描述示例**：

```
这是一个天气Agent。可以查询天气。很好用。
```

### 5.4 能力标签选择

选择描述性的、用户可能搜索的标签：

```python
# 好标签
capabilities=[
    "weather-forecast",      # 具体功能
    "location-based",        # 特性
    "real-time",             # 时效性
    "multi-language",        # 支持语言
]

# 避免过于宽泛的标签
capabilities=[
    "ai",                    # 太宽泛
    "service",               # 无意义
]
```

---

## 6. 部署与运行

### 6.1 本地开发

适合开发和测试：

```python
# 本地运行，端口8001
await agent.start_server(host="127.0.0.1", port=8001)
```

### 6.2 生产部署

#### 6.2.1 使用Docker

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
# 构建并运行
docker build -t my-agent .
docker run -p 8001:8001 my-agent
```

#### 6.2.2 使用云服务

推荐的云服务部署：
- **AWS**: ECS, Lambda (适合轻量任务)
- **GCP**: Cloud Run, App Engine
- **阿里云**: 函数计算, ECS
- **Vercel**: 适合轻量级Agent

#### 6.2.3 配置域名和HTTPS

生产环境必须使用HTTPS：

```python
# 使用反向代理（Nginx/Traefik）
# 或内置HTTPS（需要证书）

# 推荐架构:
# User ──HTTPS──▶ CDN/Load Balancer ──▶ Nginx ──HTTP──▶ Agent Server
```

### 6.3 使用Agent Host多Agent部署

如果你想在一个服务器运行多个Agent：

```python
from aac_protocol.creator.sdk.server import AgentHost

# 创建Host
host = AgentHost(title="My Agent Cluster")

# 注册多个Agent
host.register_agent(agent1_card, agent1_handler)
host.register_agent(agent2_card, agent2_handler)
host.register_agent(agent3_card, agent3_handler)

# 启动（所有Agent共享一个端口，通过ID路由）
await host.run(port=8000)
```

---

## 7. 定价策略

### 7.1 定价原则

**成本导向定价**：
```
价格 = 计算成本 + 维护成本 + 期望利润
```

**市场导向定价**：
```
参考同类Agent价格，可略低以获得初期用户
```

**价值导向定价**：
```
基于为用户创造的价值定价
```

### 7.2 定价建议

| Agent类型 | 建议价格范围 | 说明 |
|-----------|-------------|------|
| 简单文本处理 | 0.5-2 AAC | 低计算成本 |
| 数据分析 | 3-10 AAC | 需要计算资源 |
| 图像处理 | 5-20 AAC | GPU成本高 |
| 复杂AI推理 | 10-50 AAC | 大模型API成本 |

### 7.3 动态定价策略

```python
# 示例：根据负载动态调整
class DynamicPricingAgent(Agent):
    async def get_current_price(self) -> float:
        base_price = 5.0
        
        # 高峰期加价
        if self.is_peak_hours():
            return base_price * 1.5
        
        # 低负载时降价吸引用户
        if self.queue_size() < 3:
            return base_price * 0.8
        
        return base_price
```

### 7.4 免费策略

初期可考虑部分免费：

```python
# 新用户首次免费
# 或每日限量免费

FREE_QUOTA = 10  # 每日前10次免费

async def execute_task(self, task_input: TaskInput) -> TaskOutput:
    user_free_used = await self.get_user_free_quota(task_input.user_id)
    
    if user_free_used < FREE_QUOTA:
        # 免费处理
        pass
    else:
        # 正常计费
        pass
```

---

## 8. 可信度建设

### 8.1 可信度的重要性

可信度直接影响：
- **用户选择**: 高可信度Agent更容易被选中
- **排序权重**: 搜索结果中排名更靠前
- **价格溢价**: 可收取更高价格

### 8.2 提升可信度的方法

#### 8.2.1 初期阶段（0-10个任务）

```
策略: 低价 + 高质量 + 主动邀请评价

1. 定价低于市场30%
2. 确保100%成功率
3. 快速响应（< 1秒）
4. 主动请满意用户留评
```

#### 8.2.2 成长阶段（10-100个任务）

```
策略: 稳定服务 + 积累口碑

1. 保持99%+成功率
2. 完善错误处理
3. 添加更多能力
4. 响应用户反馈
```

#### 8.2.3 成熟阶段（100+任务）

```
策略: 品牌建设 + 差异化

1. 形成特色优势
2. 建立专业形象
3. 适当提高价格
4. 拓展新能力
```

### 8.3 避免信誉损失

**绝对避免**：
- 服务经常失败
- 响应极慢（>30秒）
- 输出质量差
- 虚假宣传能力

**应对差评**：
```python
async def on_task_complete(self, task_id, output, duration):
    # 如果用户给了低分，主动联系
    if task.user_rating and task.user_rating < 3:
        await self.notify_creator(
            f"Task {task_id} received low rating. "
            f"Feedback: {task.user_feedback}"
        )
```

---

## 9. 高级功能

### 9.1 流式响应

对于长时间任务，提供进度更新：

```python
async def execute_task(self, task_input: TaskInput) -> TaskOutput:
    # 发送进度更新
    await self.send_stream_update(task_id, {
        "type": "progress",
        "percent": 25,
        "message": "Processing data..."
    })
    
    # 处理中...
    await asyncio.sleep(1)
    
    await self.send_stream_update(task_id, {
        "type": "progress",
        "percent": 75,
        "message": "Generating report..."
    })
    
    # 返回结果
    return TaskOutput(content="...")
```

### 9.2 任务验证

在接收任务前验证输入：

```python
async def validate_input(self, task_input: TaskInput) -> bool:
    # 检查必需字段
    if not task_input.content:
        return False
    
    # 检查文件大小限制
    for attachment in task_input.attachments:
        if attachment.get("size", 0) > 10 * 1024 * 1024:  # 10MB
            return False
    
    return True
```

### 9.3 任务批处理

支持批量处理提高效率：

```python
async def execute_batch(self, task_inputs: List[TaskInput]) -> List[TaskOutput]:
    # 批量处理多个任务
    results = []
    
    # 并行处理
    tasks = [self.process_single(inp) for inp in task_inputs]
    results = await asyncio.gather(*tasks)
    
    return results
```

### 9.4 错误处理

完善的错误处理提升用户体验：

```python
async def execute_task(self, task_input: TaskInput) -> TaskOutput:
    try:
        result = await self.process(task_input)
        return TaskOutput(content=result)
        
    except ValidationError as e:
        return TaskOutput(
            content="",
            metadata={"error": f"Invalid input: {e}"}
        )
        
    except TimeoutError:
        return TaskOutput(
            content="",
            metadata={"error": "Processing timeout. Please try again."}
        )
        
    except Exception as e:
        # 记录错误，通知创作者
        await self.report_error(e)
        return TaskOutput(
            content="",
            metadata={"error": "Internal error. Creator notified."}
        )
```

---

## 10. 最佳实践

### 10.1 代码组织

```
my-agent/
├── src/
│   ├── __init__.py
│   ├── agent.py          # Agent类
│   ├── models.py         # 数据模型
│   ├── services/         # 业务逻辑
│   │   ├── __init__.py
│   │   ├── processor.py
│   │   └── validator.py
│   └── utils/            # 工具函数
│       ├── __init__.py
│       └── helpers.py
├── tests/                # 测试
├── config/               # 配置
├── docs/                 # 文档
├── requirements.txt
└── README.md
```

### 10.2 性能优化

```python
# 1. 连接池复用
class MyAgent(Agent):
    def __init__(self, ...):
        super().__init__(...)
        self.http_client = httpx.AsyncClient()
    
    async def execute_task(self, task_input):
        # 复用连接
        response = await self.http_client.get(...)

# 2. 缓存热点数据
@functools.lru_cache(maxsize=100)
def get_cached_data(key):
    return expensive_query(key)

# 3. 异步I/O
async def process(self, data):
    # 使用asyncio.gather并行处理
    results = await asyncio.gather(*[
        self.process_item(item)
        for item in data
    ])
```

### 10.3 安全实践

```python
# 1. 输入验证
import re

def sanitize_input(content: str) -> str:
    # 移除危险字符
    return re.sub(r'[<>"\']', '', content)

# 2. 资源限制
MAX_PROCESSING_TIME = 30  # 秒
MAX_MEMORY_MB = 512

# 3. 敏感信息保护
API_KEYS = os.environ.get("API_KEYS")  # 不要硬编码
```

### 10.4 监控与日志

```python
import logging

logger = logging.getLogger(__name__)

class MonitoredAgent(Agent):
    async def on_task_start(self, task_id, task_input):
        logger.info(f"Task {task_id} started")
        await self.record_metric("task_start", 1)
    
    async def on_task_complete(self, task_id, output, duration_ms):
        logger.info(f"Task {task_id} completed in {duration_ms}ms")
        await self.record_metric("task_duration", duration_ms)
        
        if duration_ms > 5000:  # 慢任务告警
            logger.warning(f"Slow task detected: {task_id}")
    
    async def on_task_error(self, task_id, error):
        logger.error(f"Task {task_id} failed: {error}")
        await self.send_alert(f"Task failure: {task_id}")
```

---

## 11. 故障排除

### 11.1 常见问题

#### Q: Agent注册失败

```
可能原因：
1. 网络连接问题
2. Creator ID无效
3. Agent名称格式错误

解决方案：
- 检查网络连接
- 确认Creator已注册
- 检查Agent名称（小写字母、数字、连字符）
```

#### Q: 任务执行超时

```
可能原因：
1. 处理逻辑太慢
2. 外部API响应慢
3. 资源不足

解决方案：
- 优化处理逻辑
- 设置更短的API超时
- 增加服务器资源
- 使用流式响应
```

#### Q: 用户评分低

```
可能原因：
1. 输出质量不符合期望
2. 响应太慢
3. 描述与实际不符

解决方案：
- 改进Agent能力
- 优化性能
- 更新描述使其准确
```

### 11.2 调试技巧

```bash
# 1. 查看详细日志
export AAC_DEBUG=1
python agent.py

# 2. 本地测试
python -m pytest tests/

# 3. 检查Agent状态
curl http://localhost:8001/health

# 4. 手动触发任务
curl -X POST http://localhost:8001/rpc \
  -d '{"jsonrpc":"2.0","method":"task/execute",...}'
```

### 11.3 获取帮助

遇到问题时的求助途径：

1. **文档**: 查阅本指南和API文档
2. **示例**: 参考官方示例代码
3. **社区**: GitHub Discussions
4. **Issues**: 在GitHub提交Issue

---

## 附录

### 命令速查表

| 命令 | 说明 |
|------|------|
| `aac-creator init` | 初始化环境 |
| `aac-creator create-agent` | 创建Agent |
| `aac-creator list-agents` | 列出Agent |
| `aac-creator start-agent <id>` | 启动Agent |
| `aac-creator stats` | 查看统计 |

### 资源链接

- **GitHub**: https://github.com/AAC-Protocol/aac-protocol
- **文档**: https://docs.aac-protocol.org
- **示例**: https://github.com/AAC-Protocol/examples

---

**作者**: 宋梓铭 (Jack Song / Ziming Song)  
**来自**: 北京市朝阳区赫德

**祝你创作愉快！在AAC协议生态中创造有价值的服务！**

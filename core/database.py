"""
AAC Protocol Database Interface

Provides database operations for all AAC Protocol entities.
Uses SQLAlchemy for ORM with support for SQLite (dev) and PostgreSQL (prod).
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, DateTime,
    Text, JSON, select, update, delete, desc, asc
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker

from .models import (
    AgentCard, AgentID, Task, Payment, Dispute, User, Creator,
    Transaction, Rating, AgentStatus, TaskStatus, PaymentStatus,
    DisputeStatus
)

Base = declarative_base()


class AgentRecord(Base):
    """Database record for Agent"""
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    sequence_id = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    creator_id = Column(String, nullable=False, index=True)
    creator_name = Column(String)
    price_per_task = Column(Float, nullable=False)
    credibility_score = Column(Float, default=3.0)
    total_ratings = Column(Integer, default=0)
    public_trust_score = Column(Float, default=0.0)
    completed_tasks = Column(Integer, default=0)
    capabilities = Column(JSON, default=list)
    input_types = Column(JSON, default=list)
    output_types = Column(JSON, default=list)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    endpoint_url = Column(String, nullable=False)
    documentation_url = Column(String)


class TaskRecord(Base):
    """Database record for Task"""
    __tablename__ = "tasks"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    agent_id = Column(String, nullable=False, index=True)
    input_content = Column(Text, nullable=False)
    input_attachments = Column(JSON, default=list)
    input_metadata = Column(JSON, default=dict)
    output_content = Column(Text)
    output_attachments = Column(JSON, default=list)
    output_metadata = Column(JSON, default=dict)
    status = Column(String, default="pending")
    error_message = Column(Text)
    price_locked = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    deadline = Column(DateTime)
    user_rating = Column(Float)
    user_feedback = Column(Text)


class PaymentRecord(Base):
    """Database record for Payment"""
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False, index=True)
    from_user_id = Column(String, nullable=False)
    to_agent_id = Column(String, nullable=False)
    to_creator_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)
    dispute_id = Column(String)


class DisputeRecord(Base):
    """Database record for Dispute"""
    __tablename__ = "disputes"
    
    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=False)
    creator_id = Column(String, nullable=False)
    user_claim = Column(Text, nullable=False)
    claimed_amount = Column(Float, nullable=False)
    user_evidence = Column(JSON, default=list)
    agent_evidence = Column(JSON, default=list)
    status = Column(String, default="open")
    current_level = Column(Integer, default=1)
    level_1_arbitrator = Column(String)
    level_2_arbitrators = Column(JSON, default=list)
    level_3_arbitrators = Column(JSON, default=list)
    level_1_decision = Column(JSON)
    level_2_decisions = Column(JSON, default=list)
    level_3_decisions = Column(JSON, default=list)
    final_decision = Column(String)
    final_intent = Column(String)
    final_compensation = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    escalated_at = Column(DateTime)
    resolved_at = Column(DateTime)
    escalation_requested_by = Column(String)


class UserRecord(Base):
    """Database record for User"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True)
    name = Column(String)
    email = Column(String)
    token_balance = Column(Float, default=1000.0)
    total_tasks_submitted = Column(Integer, default=0)
    total_spent = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class CreatorRecord(Base):
    """Database record for Creator"""
    __tablename__ = "creators"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String)
    token_balance = Column(Float, default=1000.0)
    total_earned = Column(Float, default=0.0)
    agent_ids = Column(JSON, default=list)
    total_tasks_completed = Column(Integer, default=0)
    average_rating = Column(Float, default=0.0)
    is_verified = Column(Integer, default=0)  # SQLite boolean
    trust_score = Column(Float, default=50.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)


class TransactionRecord(Base):
    """Database record for Transaction"""
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True)
    from_address = Column(String, nullable=False, index=True)
    to_address = Column(String, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    task_id = Column(String)
    dispute_id = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    signature = Column(String)


class Database:
    """
    Main database interface for AAC Protocol
    
    Supports both sync and async operations.
    """
    
    def __init__(self, database_url: str = "sqlite+aiosqlite:///./aac_protocol.db"):
        self.database_url = database_url
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def create_tables(self):
        """Create all database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self):
        """Drop all database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    @asynccontextmanager
    async def session(self):
        """Get database session context manager"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    # Agent operations
    async def create_agent(self, agent: AgentCard) -> AgentCard:
        """Create new agent record"""
        async with self.session() as session:
            record = AgentRecord(
                id=agent.id.full_id,
                name=agent.id.name,
                sequence_id=agent.id.sequence_id,
                description=agent.description,
                creator_id=agent.creator_id,
                creator_name=agent.creator_name,
                price_per_task=agent.price_per_task,
                credibility_score=agent.credibility_score,
                total_ratings=agent.total_ratings,
                public_trust_score=agent.public_trust_score,
                completed_tasks=agent.completed_tasks,
                capabilities=agent.capabilities,
                input_types=agent.input_types,
                output_types=agent.output_types,
                status=agent.status.value,
                created_at=agent.created_at,
                updated_at=agent.updated_at,
                endpoint_url=agent.endpoint_url,
                documentation_url=agent.documentation_url,
            )
            session.add(record)
            return agent
    
    async def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        """Get agent by ID"""
        async with self.session() as session:
            result = await session.execute(
                select(AgentRecord).where(AgentRecord.id == agent_id)
            )
            record = result.scalar_one_or_none()
            if record:
                return self._agent_from_record(record)
            return None
    
    async def update_agent(self, agent: AgentCard) -> AgentCard:
        """Update agent record"""
        async with self.session() as session:
            await session.execute(
                update(AgentRecord)
                .where(AgentRecord.id == agent.id.full_id)
                .values(
                    description=agent.description,
                    price_per_task=agent.price_per_task,
                    credibility_score=agent.credibility_score,
                    total_ratings=agent.total_ratings,
                    public_trust_score=agent.public_trust_score,
                    completed_tasks=agent.completed_tasks,
                    capabilities=agent.capabilities,
                    input_types=agent.input_types,
                    output_types=agent.output_types,
                    status=agent.status.value,
                    updated_at=datetime.utcnow(),
                    endpoint_url=agent.endpoint_url,
                )
            )
            return agent
    
    async def list_agents(
        self,
        status: Optional[AgentStatus] = None,
        creator_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AgentCard]:
        """List agents with optional filters"""
        async with self.session() as session:
            query = select(AgentRecord)
            
            if status:
                query = query.where(AgentRecord.status == status.value)
            if creator_id:
                query = query.where(AgentRecord.creator_id == creator_id)
            
            query = query.order_by(desc(AgentRecord.public_trust_score))
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            records = result.scalars().all()
            return [self._agent_from_record(r) for r in records]
    
    def _agent_from_record(self, record: AgentRecord) -> AgentCard:
        """Convert database record to AgentCard model"""
        return AgentCard(
            id=AgentID(name=record.name, sequence_id=record.sequence_id),
            name=record.name,
            description=record.description,
            creator_id=record.creator_id,
            creator_name=record.creator_name,
            price_per_task=record.price_per_task,
            credibility_score=record.credibility_score,
            total_ratings=record.total_ratings,
            public_trust_score=record.public_trust_score,
            completed_tasks=record.completed_tasks,
            capabilities=record.capabilities or [],
            input_types=record.input_types or [],
            output_types=record.output_types or [],
            status=AgentStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            endpoint_url=record.endpoint_url,
            documentation_url=record.documentation_url,
        )
    
    # Task operations
    async def create_task(self, task: Task) -> Task:
        """Create new task record"""
        async with self.session() as session:
            record = TaskRecord(
                id=task.id,
                user_id=task.user_id,
                agent_id=task.agent_id,
                input_content=task.input.content,
                input_attachments=task.input.attachments,
                input_metadata=task.input.metadata,
                status=task.status.value,
                price_locked=task.price_locked,
                created_at=task.created_at,
                deadline=task.deadline,
            )
            session.add(record)
            return task
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        async with self.session() as session:
            result = await session.execute(
                select(TaskRecord).where(TaskRecord.id == task_id)
            )
            record = result.scalar_one_or_none()
            if record:
                return self._task_from_record(record)
            return None
    
    async def update_task(self, task: Task) -> Task:
        """Update task record"""
        async with self.session() as session:
            values = {
                "status": task.status.value,
                "error_message": task.error_message,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "user_rating": task.user_rating,
                "user_feedback": task.user_feedback,
            }
            
            if task.output:
                values.update({
                    "output_content": task.output.content,
                    "output_attachments": task.output.attachments,
                    "output_metadata": task.output.metadata,
                })
            
            await session.execute(
                update(TaskRecord)
                .where(TaskRecord.id == task.id)
                .values(**values)
            )
            return task
    
    def _task_from_record(self, record: TaskRecord) -> Task:
        """Convert database record to Task model"""
        from .models import TaskInput, TaskOutput
        
        task = Task(
            id=record.id,
            user_id=record.user_id,
            agent_id=record.agent_id,
            input=TaskInput(
                content=record.input_content,
                attachments=record.input_attachments or [],
                metadata=record.input_metadata or {},
            ),
            status=TaskStatus(record.status),
            error_message=record.error_message,
            price_locked=record.price_locked,
            created_at=record.created_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            deadline=record.deadline,
            user_rating=record.user_rating,
            user_feedback=record.user_feedback,
        )
        
        if record.output_content:
            task.output = TaskOutput(
                content=record.output_content,
                attachments=record.output_attachments or [],
                metadata=record.output_metadata or {},
            )
        
        return task
    
    # User operations
    async def create_user(self, user: User) -> User:
        """Create new user record"""
        async with self.session() as session:
            record = UserRecord(
                id=user.id,
                name=user.name,
                email=user.email,
                token_balance=user.token_balance,
                total_tasks_submitted=user.total_tasks_submitted,
                total_spent=user.total_spent,
                created_at=user.created_at,
                last_active=user.last_active,
            )
            session.add(record)
            return user
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with self.session() as session:
            result = await session.execute(
                select(UserRecord).where(UserRecord.id == user_id)
            )
            record = result.scalar_one_or_none()
            if record:
                return self._user_from_record(record)
            return None
    
    async def update_user_balance(self, user_id: str, new_balance: float):
        """Update user token balance"""
        async with self.session() as session:
            await session.execute(
                update(UserRecord)
                .where(UserRecord.id == user_id)
                .values(token_balance=new_balance, last_active=datetime.utcnow())
            )
    
    def _user_from_record(self, record: UserRecord) -> User:
        """Convert database record to User model"""
        return User(
            id=record.id,
            name=record.name,
            email=record.email,
            token_balance=record.token_balance,
            total_tasks_submitted=record.total_tasks_submitted,
            total_spent=record.total_spent,
            created_at=record.created_at,
            last_active=record.last_active,
        )
    
    # Creator operations
    async def create_creator(self, creator: Creator) -> Creator:
        """Create new creator record"""
        async with self.session() as session:
            record = CreatorRecord(
                id=creator.id,
                name=creator.name,
                email=creator.email,
                token_balance=creator.token_balance,
                total_earned=creator.total_earned,
                agent_ids=creator.agent_ids,
                total_tasks_completed=creator.total_tasks_completed,
                average_rating=creator.average_rating,
                is_verified=1 if creator.is_verified else 0,
                trust_score=creator.trust_score,
                created_at=creator.created_at,
                last_active=creator.last_active,
            )
            session.add(record)
            return creator
    
    async def get_creator(self, creator_id: str) -> Optional[Creator]:
        """Get creator by ID"""
        async with self.session() as session:
            result = await session.execute(
                select(CreatorRecord).where(CreatorRecord.id == creator_id)
            )
            record = result.scalar_one_or_none()
            if record:
                return self._creator_from_record(record)
            return None
    
    async def update_creator(self, creator: Creator) -> Creator:
        """Update creator record"""
        async with self.session() as session:
            await session.execute(
                update(CreatorRecord)
                .where(CreatorRecord.id == creator.id)
                .values(
                    token_balance=creator.token_balance,
                    total_earned=creator.total_earned,
                    agent_ids=creator.agent_ids,
                    total_tasks_completed=creator.total_tasks_completed,
                    average_rating=creator.average_rating,
                    trust_score=creator.trust_score,
                    last_active=datetime.utcnow(),
                )
            )
            return creator
    
    def _creator_from_record(self, record: CreatorRecord) -> Creator:
        """Convert database record to Creator model"""
        return Creator(
            id=record.id,
            name=record.name,
            email=record.email,
            token_balance=record.token_balance,
            total_earned=record.total_earned,
            agent_ids=record.agent_ids or [],
            total_tasks_completed=record.total_tasks_completed,
            average_rating=record.average_rating,
            is_verified=bool(record.is_verified),
            trust_score=record.trust_score,
            created_at=record.created_at,
            last_active=record.last_active,
        )
    
    # Payment operations
    async def create_payment(self, payment: Payment) -> Payment:
        """Create new payment record"""
        async with self.session() as session:
            record = PaymentRecord(
                id=payment.id,
                task_id=payment.task_id,
                from_user_id=payment.from_user_id,
                to_agent_id=payment.to_agent_id,
                to_creator_id=payment.to_creator_id,
                amount=payment.amount,
                status=payment.status.value,
                created_at=payment.created_at,
                executed_at=payment.executed_at,
                dispute_id=payment.dispute_id,
            )
            session.add(record)
            return payment
    
    async def update_payment_status(self, payment_id: str, status: PaymentStatus):
        """Update payment status"""
        async with self.session() as session:
            await session.execute(
                update(PaymentRecord)
                .where(PaymentRecord.id == payment_id)
                .values(
                    status=status.value,
                    executed_at=datetime.utcnow() if status in [PaymentStatus.RELEASED, PaymentStatus.REFUNDED] else None
                )
            )
    
    # Dispute operations
    async def create_dispute(self, dispute: Dispute) -> Dispute:
        """Create new dispute record"""
        async with self.session() as session:
            record = DisputeRecord(
                id=dispute.id,
                task_id=dispute.task_id,
                user_id=dispute.user_id,
                agent_id=dispute.agent_id,
                creator_id=dispute.creator_id,
                user_claim=dispute.user_claim,
                claimed_amount=dispute.claimed_amount,
                user_evidence=[e.model_dump() for e in dispute.user_evidence],
                agent_evidence=[e.model_dump() for e in dispute.agent_evidence],
                status=dispute.status.value,
                current_level=dispute.current_level.value,
                level_1_arbitrator=dispute.level_1_arbitrator,
                level_2_arbitrators=dispute.level_2_arbitrators,
                level_3_arbitrators=dispute.level_3_arbitrators,
                level_1_decision=dispute.level_1_decision.model_dump() if dispute.level_1_decision else None,
                level_2_decisions=[d.model_dump() for d in dispute.level_2_decisions],
                level_3_decisions=[d.model_dump() for d in dispute.level_3_decisions],
                final_decision=dispute.final_decision.value if dispute.final_decision else None,
                final_intent=dispute.final_intent.value if dispute.final_intent else None,
                final_compensation=dispute.final_compensation,
                created_at=dispute.created_at,
                escalated_at=dispute.escalated_at,
                resolved_at=dispute.resolved_at,
                escalation_requested_by=dispute.escalation_requested_by,
            )
            session.add(record)
            return dispute
    
    async def get_dispute(self, dispute_id: str) -> Optional[Dispute]:
        """Get dispute by ID"""
        async with self.session() as session:
            result = await session.execute(
                select(DisputeRecord).where(DisputeRecord.id == dispute_id)
            )
            record = result.scalar_one_or_none()
            if record:
                return self._dispute_from_record(record)
            return None
    
    async def update_dispute(self, dispute: Dispute) -> Dispute:
        """Update dispute record"""
        async with self.session() as session:
            await session.execute(
                update(DisputeRecord)
                .where(DisputeRecord.id == dispute.id)
                .values(
                    status=dispute.status.value,
                    current_level=dispute.current_level.value,
                    level_1_arbitrator=dispute.level_1_arbitrator,
                    level_2_arbitrators=dispute.level_2_arbitrators,
                    level_3_arbitrators=dispute.level_3_arbitrators,
                    level_1_decision=dispute.level_1_decision.model_dump() if dispute.level_1_decision else None,
                    level_2_decisions=[d.model_dump() for d in dispute.level_2_decisions],
                    level_3_decisions=[d.model_dump() for d in dispute.level_3_decisions],
                    final_decision=dispute.final_decision.value if dispute.final_decision else None,
                    final_intent=dispute.final_intent.value if dispute.final_intent else None,
                    final_compensation=dispute.final_compensation,
                    escalated_at=dispute.escalated_at,
                    resolved_at=dispute.resolved_at,
                )
            )
            return dispute
    
    def _dispute_from_record(self, record: DisputeRecord) -> Dispute:
        """Convert database record to Dispute model"""
        from .models import DisputeEvidence, ArbitratorDecision
        
        dispute = Dispute(
            id=record.id,
            task_id=record.task_id,
            user_id=record.user_id,
            agent_id=record.agent_id,
            creator_id=record.creator_id,
            user_claim=record.user_claim,
            claimed_amount=record.claimed_amount,
            status=DisputeStatus(record.status),
            current_level=ArbitrationLevel(record.current_level),
            level_1_arbitrator=record.level_1_arbitrator,
            level_2_arbitrators=record.level_2_arbitrators or [],
            level_3_arbitrators=record.level_3_arbitrators or [],
            final_compensation=record.final_compensation,
            created_at=record.created_at,
            escalated_at=record.escalated_at,
            resolved_at=record.resolved_at,
            escalation_requested_by=record.escalation_requested_by,
        )
        
        # Parse evidence
        if record.user_evidence:
            dispute.user_evidence = [DisputeEvidence(**e) for e in record.user_evidence]
        if record.agent_evidence:
            dispute.agent_evidence = [DisputeEvidence(**e) for e in record.agent_evidence]
        
        # Parse decisions
        if record.level_1_decision:
            dispute.level_1_decision = ArbitratorDecision(**record.level_1_decision)
        if record.level_2_decisions:
            dispute.level_2_decisions = [ArbitratorDecision(**d) for d in record.level_2_decisions]
        if record.level_3_decisions:
            dispute.level_3_decisions = [ArbitratorDecision(**d) for d in record.level_3_decisions]
        
        if record.final_decision:
            from .models import ArbitrationResult
            dispute.final_decision = ArbitrationResult(record.final_decision)
        if record.final_intent:
            from .models import Intent
            dispute.final_intent = Intent(record.final_intent)
        
        return dispute
    
    # Transaction operations
    async def record_transaction(self, transaction: Transaction) -> Transaction:
        """Record a token transaction"""
        async with self.session() as session:
            record = TransactionRecord(
                id=transaction.id,
                from_address=transaction.from_address,
                to_address=transaction.to_address,
                amount=transaction.amount,
                type=transaction.type,
                task_id=transaction.task_id,
                dispute_id=transaction.dispute_id,
                timestamp=transaction.timestamp,
                signature=transaction.signature,
            )
            session.add(record)
            return transaction
    
    async def get_transactions(self, address: str, limit: int = 100) -> List[Transaction]:
        """Get transactions for an address"""
        async with self.session() as session:
            result = await session.execute(
                select(TransactionRecord)
                .where(
                    (TransactionRecord.from_address == address) |
                    (TransactionRecord.to_address == address)
                )
                .order_by(desc(TransactionRecord.timestamp))
                .limit(limit)
            )
            records = result.scalars().all()
            return [self._transaction_from_record(r) for r in records]
    
    def _transaction_from_record(self, record: TransactionRecord) -> Transaction:
        """Convert database record to Transaction model"""
        return Transaction(
            id=record.id,
            from_address=record.from_address,
            to_address=record.to_address,
            amount=record.amount,
            type=record.type,
            task_id=record.task_id,
            dispute_id=record.dispute_id,
            timestamp=record.timestamp,
            signature=record.signature,
        )

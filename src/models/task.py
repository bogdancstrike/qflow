import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import Config

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_type = Column(String(50), nullable=False)
    input_data = Column(JSONB, nullable=False)
    outputs = Column(JSONB, nullable=False)  # list of requested output types
    execution_plan = Column(JSONB, nullable=False)  # DAG execution plan
    status = Column(String(20), nullable=False, default="PENDING")
    current_step = Column(String(100), nullable=True)
    step_results = Column(JSONB, nullable=True, default=dict)
    workflow_variables = Column(JSONB, nullable=True, default=dict)
    final_output = Column(JSONB, nullable=True)
    error = Column(JSONB, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "input_type": self.input_type,
            "input_data": self.input_data,
            "outputs": self.outputs,
            "execution_plan": self.execution_plan,
            "status": self.status,
            "current_step": self.current_step,
            "step_results": self.step_results,
            "workflow_variables": self.workflow_variables,
            "final_output": self.final_output,
            "error": self.error,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


_engine = None
_SessionFactory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(Config.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
    return _engine


def get_session():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory()


def init_db():
    Base.metadata.create_all(get_engine())

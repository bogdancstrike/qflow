import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, JSON, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import Config

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    input_type = Column(String(50), nullable=False)
    input_data = Column(JSON, nullable=False)
    outputs = Column(JSON, nullable=False)
    execution_plan = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    current_step = Column(String(100), nullable=True)
    step_results = Column(JSON, nullable=True, default=dict)
    workflow_variables = Column(JSON, nullable=True, default=dict)
    final_output = Column(JSON, nullable=True)
    error = Column(JSON, nullable=True)
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
        kwargs = {"pool_pre_ping": True}
        if Config.DATABASE_URL.startswith("postgresql"):
            kwargs.update({"pool_size": 10, "max_overflow": 20})
        _engine = create_engine(Config.DATABASE_URL, **kwargs)
    return _engine


def get_session():
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory()


def init_db():
    Base.metadata.create_all(get_engine())

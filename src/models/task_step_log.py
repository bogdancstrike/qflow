import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship

from src.models.task import Base


class TaskStepLog(Base):
    __tablename__ = "task_step_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False, index=True)
    task_ref = Column(String(100), nullable=False)
    task_type = Column(String(50), nullable=False)
    attempt = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False)
    request_payload = Column(JSON, nullable=True)
    response_payload = Column(JSON, nullable=True)
    branch_taken = Column(String(100), nullable=True)
    iteration = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": str(self.id),
            "task_id": str(self.task_id),
            "task_ref": self.task_ref,
            "task_type": self.task_type,
            "attempt": self.attempt,
            "status": self.status,
            "request_payload": self.request_payload,
            "response_payload": self.response_payload,
            "branch_taken": self.branch_taken,
            "iteration": self.iteration,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

import os

from dotenv import load_dotenv

load_dotenv()

from framework.commons.logger import logger


class Config:
    # Application
    DEV_MODE = os.getenv("DEV_MODE", "true").lower() in ("1", "true", "yes")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")

    # Kafka
    WORKER_NAME = os.getenv("WORKER_NAME", "ai-flow-orchestrator")
    KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")
    KAFKA_TASK_TOPIC_IN = os.getenv("KAFKA_TASK_TOPIC_IN", "flow.tasks.in")
    KAFKA_TASK_TOPIC_OUT = os.getenv("KAFKA_TASK_TOPIC_OUT", "flow.tasks.out")
    KAFKA_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "flow.tasks.dlq")
    KAFKA_COMMIT_STRATEGY = os.getenv("KAFKA_COMMIT_STRATEGY", "before")
    ERROR_TOPIC = os.getenv("ERROR_TOPIC", "flow.errors")

    # Poll tuning
    KAFKA_POLL_TIMEOUT_MS = int(os.getenv("KAFKA_POLL_TIMEOUT_MS", "1"))
    KAFKA_POLL_MAX_RECORDS = int(os.getenv("KAFKA_POLL_MAX_RECORDS", "200"))
    KAFKA_IDLE_SLEEP_SEC = float(os.getenv("KAFKA_IDLE_SLEEP_SEC", "0"))
    KAFKA_COMMIT_TICK_SEC = float(os.getenv("KAFKA_COMMIT_TICK_SEC", "0.2"))
    KAFKA_MAX_JOBS_PER_TP_PER_TICK = int(os.getenv("KAFKA_MAX_JOBS_PER_TP_PER_TICK", "20"))

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = os.getenv("REDIS_PORT", "6379")
    REDIS_DB = os.getenv("REDIS_DB", "0")
    REDIS_MAX_CONNECTIONS = os.getenv("REDIS_MAX_CONNECTIONS", "50")
    REDIS_SOCKET_TIMEOUT = os.getenv("REDIS_SOCKET_TIMEOUT", "5.0")
    REDIS_CONNECT_TIMEOUT = os.getenv("REDIS_CONNECT_TIMEOUT", "5.0")
    REDIS_RETRY_ON_TIMEOUT = os.getenv("REDIS_RETRY_ON_TIMEOUT", "true")

    # PostgreSQL
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://qf:qf@localhost:5432/ai_flow")

    # Tracing
    ENABLE_TRACING = os.getenv("ENABLE_TRACING", "false").lower() in ("1", "true", "yes")
    OTLP_ENDPOINT = os.getenv("QSINT_OTLP_ENDPOINT", "http://localhost:4317")

    # AI Service URLs
    AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8000")
    AI_STT_URL = os.getenv("AI_STT_URL", "http://localhost:8001")
    AI_STT_TOKEN = os.getenv("AI_STT_TOKEN", "dev-token")
    AI_NER_URL = os.getenv("AI_NER_URL", "http://localhost:8002")
    AI_TRANSLATE_URL = os.getenv("AI_TRANSLATE_URL", "http://localhost:8003")
    AI_LANGDETECT_URL = os.getenv("AI_LANGDETECT_URL", "http://localhost:8004")
    AI_SENTIMENT_URL = os.getenv("AI_SENTIMENT_URL", "http://localhost:8005")
    AI_SUMMARY_URL = os.getenv("AI_SUMMARY_URL", "http://localhost:8006")
    AI_TAXONOMY_URL = os.getenv("AI_TAXONOMY_URL", "http://localhost:8007")

    # File uploads
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/tmp/uploads")

    # Executor limits
    MAX_LOOP_ITERATIONS = int(os.getenv("MAX_LOOP_ITERATIONS", "100"))
    FORK_JOIN_MAX_WORKERS = int(os.getenv("FORK_JOIN_MAX_WORKERS", "4"))
    MAX_SUB_WORKFLOW_DEPTH = int(os.getenv("MAX_SUB_WORKFLOW_DEPTH", "10"))

    # API
    API_PORT = int(os.getenv("API_PORT", "5000"))
    SECRET_KEY = os.getenv("SECRET_KEY", "secret")

    logger.setLevel(LOG_LEVEL)

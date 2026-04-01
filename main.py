"""AI Flow Orchestrator — entry point.

Starts both the ETL (Kafka consumer) and the HTTP API in a single process
using the QF Framework's FrameworkApp.

The ETL worker consumes from flow.tasks.in and executes resolved pipelines.
The HTTP API handles task creation, status queries, and management.

Environment variables of interest
----------------------------------
  DEV_MODE=true              — mock all AI service HTTP calls (default: true)
  ENABLE_TRACING=true        — enable OTel span export to Jaeger (default: false)
  QSINT_OTLP_ENDPOINT       — OTLP gRPC endpoint, e.g. http://localhost:4317
  KAFKA_BOOTSTRAP_SERVERS    — Kafka broker address (default: localhost:9094)
  DATABASE_URL               — PostgreSQL connection string
  API_PORT                   — HTTP listen port (default: 5000)
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

from src.config import Config
from framework.app import FrameworkApp, FrameworkSettings
from framework.commons.logger import logger

def main():
    logger.info(
        f"[AI-FLOW] Starting — dev_mode={Config.DEV_MODE} "
        f"tracing={'enabled' if Config.ENABLE_TRACING else 'disabled'} "
        f"kafka={Config.KAFKA_BOOTSTRAP_SERVERS} "
        f"api_port={Config.API_PORT}"
    )

    # Initialize DB tables
    from src.models.task import init_db
    try:
        init_db()
        logger.info("[AI-FLOW] Database tables initialized")
    except Exception as e:
        logger.warning(f"[AI-FLOW] Could not initialize DB (will retry on first use): {e}")

    # Initialize template/flow registry
    from src.templating.registry import init_registry
    init_registry(str(BASE_DIR))
    logger.info("[AI-FLOW] Template registry initialized")

    settings = FrameworkSettings(
        enable_etl=True,
        enable_api=True,
        enable_dynamic_endpoints=True,

        api_host="0.0.0.0",
        api_port=Config.API_PORT,
        api_version="1.0",
        api_title="AI Flow Orchestrator API",
        api_description="On-demand AI pipeline orchestrator built on QF Framework",

        endpoint_json_path="maps/endpoint.json",

        worker_modules=["workers.flow_executor", "core.subflow_workers"],
        kafka_bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
        consumer_name=Config.WORKER_NAME,

        enable_tracing=Config.ENABLE_TRACING,
        otlp_endpoint=Config.OTLP_ENDPOINT,
        service_name=Config.WORKER_NAME,
    )

    fw = FrameworkApp(settings, app_root=BASE_DIR)
    handles = fw.run()

    if handles.app:
        logger.info(f"[AI-FLOW] API listening on {settings.api_host}:{settings.api_port}")
        handles.app.run(host=settings.api_host, port=settings.api_port, debug=False)


if __name__ == "__main__":
    main()

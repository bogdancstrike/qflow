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
  DRAIN_TIMEOUT_SEC          — graceful shutdown drain timeout (default: 30)
"""

import os
import signal
import sys
import threading
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

# Monkey-patch kafka-python OffsetAndMetadata to supply default leader_epoch.
# The QF framework calls OffsetAndMetadata(offset, metadata) with 2 args, but
# kafka-python 2.3.0 requires 3 (offset, metadata, leader_epoch).
from collections import namedtuple as _nt
import kafka.structs as _ks
_ks.OffsetAndMetadata = _nt("OffsetAndMetadata", ["offset", "metadata", "leader_epoch"], defaults=[0])

from src.config import Config
from framework.app import FrameworkApp, FrameworkSettings
from framework.commons.logger import logger

# ---------------------------------------------------------------------------
# Graceful shutdown coordinator
# ---------------------------------------------------------------------------

_shutdown_event = threading.Event()
_active_greenlets = []  # tracked for drain-then-kill
DRAIN_TIMEOUT = int(os.getenv("DRAIN_TIMEOUT_SEC", "30"))


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    sig_name = signal.Signals(signum).name
    logger.info(f"[SHUTDOWN] Received {sig_name} — initiating graceful shutdown")
    _shutdown_event.set()


def _graceful_shutdown(fw: FrameworkApp):
    """Execute the shutdown sequence:
    1. Stop accepting new Kafka messages
    2. Drain in-flight tasks (with timeout)
    3. Force-cancel remaining greenlets
    4. Close connections
    """
    logger.info("[SHUTDOWN] Phase 1: Stopping Kafka consumer...")
    # The ETL thread is daemon — it will be interrupted when the main process exits.
    # But we try to signal it to stop first.
    try:
        fw.shutdown()
    except Exception as e:
        logger.warning(f"[SHUTDOWN] Framework shutdown call: {e}")

    logger.info(f"[SHUTDOWN] Phase 2: Draining in-flight tasks (timeout={DRAIN_TIMEOUT}s)...")
    deadline = time.time() + DRAIN_TIMEOUT

    # Wait for active greenlets to finish
    try:
        import gevent
        while _active_greenlets and time.time() < deadline:
            remaining = [g for g in _active_greenlets if not g.dead]
            if not remaining:
                break
            _active_greenlets[:] = remaining
            gevent.sleep(0.5)

        # Force-kill remaining
        remaining = [g for g in _active_greenlets if not g.dead]
        if remaining:
            logger.warning(f"[SHUTDOWN] Phase 3: Force-killing {len(remaining)} greenlet(s)")
            for g in remaining:
                g.kill(block=False)
    except ImportError:
        pass

    logger.info("[SHUTDOWN] Phase 4: Closing database connections...")
    try:
        from src.models.task import get_engine
        engine = get_engine()
        engine.dispose()
    except Exception as e:
        logger.warning(f"[SHUTDOWN] DB cleanup: {e}")

    logger.info("[SHUTDOWN] Shutdown complete")


def main():
    logger.info(
        f"[AI-FLOW] Starting — dev_mode={Config.DEV_MODE} "
        f"tracing={'enabled' if Config.ENABLE_TRACING else 'disabled'} "
        f"kafka={Config.KAFKA_BOOTSTRAP_SERVERS} "
        f"api_port={Config.API_PORT}"
    )

    # Register signal handlers
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

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

        try:
            handles.app.run(host=settings.api_host, port=settings.api_port, debug=False)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            if _shutdown_event.is_set():
                _graceful_shutdown(fw)
            else:
                logger.info("[AI-FLOW] Exiting")


if __name__ == "__main__":
    main()

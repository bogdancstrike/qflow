"""AI Flow Orchestrator — entry point.

Starts both the ETL (Kafka consumer) and the HTTP API in a single process
using the QF Framework's FrameworkApp.
"""

# GEVENT MONKEY PATCHING MUST BE FIRST
try:
    from gevent import monkey
    monkey.patch_all()
    # Try to patch psycopg2 if available
    try:
        import psycogreen.gevent
        psycogreen.gevent.patch_psycopg()
    except ImportError:
        pass
except ImportError:
    pass

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
DRAIN_TIMEOUT = int(os.getenv("DRAIN_TIMEOUT_SEC", "30"))


def _signal_handler(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    sig_name = signal.Signals(signum).name
    logger.info(f"[SHUTDOWN] Received {sig_name} — initiating graceful shutdown")
    _shutdown_event.set()


def _graceful_shutdown(fw: FrameworkApp):
    """Execute the shutdown sequence."""
    logger.info("[SHUTDOWN] Phase 1: Stopping Kafka consumer...")
    try:
        fw.shutdown()
    except Exception as e:
        logger.warning(f"[SHUTDOWN] Framework shutdown call: {e}")

    logger.info("[SHUTDOWN] Phase 2: Closing database connections...")
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

        worker_modules=["workers.flow_executor"],
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

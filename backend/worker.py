"""Background worker: OFAC sync + treasury screen + address monitoring."""
import asyncio
import logging
import os
import signal
from datetime import datetime, timezone

from services.monitor_worker import monitor_loop, run_monitor_pass
from services.sync_worker import worker_loop, run_sync_once
from services.treasury_worker import run_daily_treasury_screen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

_shutdown_event = asyncio.Event()


def _handle_signal(sig_name: str) -> None:
    logger.info(f"[worker] Received {sig_name}, initiating graceful shutdown...")
    _shutdown_event.set()


async def treasury_loop():
    interval = int(os.getenv("TREASURY_SCREEN_INTERVAL_SECONDS", "86400"))
    while not _shutdown_event.is_set():
        try:
            logger.info(f"[treasury] daily screen starting {datetime.now(timezone.utc).isoformat()}")
            report = await run_daily_treasury_screen()
            logger.info(
                f"[treasury] done: screened={report.get('screened')} "
                f"quarantined={report.get('quarantined')} sweep_ready={report.get('sweep_ready')}"
            )
        except Exception as e:
            logger.error(f"[treasury] error: {e}")
        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def main():
    # Register signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal, sig.name)

    await run_sync_once()
    try:
        await run_daily_treasury_screen()
    except Exception as e:
        logger.warning(f"[treasury] startup screen skipped: {e}")
    try:
        report = await run_monitor_pass(limit=20)
        logger.info(f"[monitor] startup: {report.get('checked')} checked")
    except Exception as e:
        logger.warning(f"[monitor] startup skipped: {e}")

    sync_interval = int(os.getenv("SYNC_INTERVAL_SECONDS", "86400"))
    tasks = [
        asyncio.create_task(worker_loop(interval_seconds=sync_interval), name="sync_worker"),
        asyncio.create_task(treasury_loop(), name="treasury_loop"),
        asyncio.create_task(monitor_loop(), name="monitor_loop"),
    ]
    # Wait until shutdown signal received
    await _shutdown_event.wait()
    logger.info("[worker] Shutdown signal received, cancelling tasks...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("[worker] All tasks cancelled. Exiting.")


if __name__ == "__main__":
    asyncio.run(main())

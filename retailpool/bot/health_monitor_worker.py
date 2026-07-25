"""
Background worker that continuously runs the shop "fire alarm" health check:
order cancellation rate and new 1-star reviews.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import async_session_factory
from retailpool.services.health_monitor_service import run_health_check_cycle

logger = logging.getLogger(__name__)

async def health_monitor_loop() -> None:
    """Infinite loop for the shop health monitor."""
    logger.info("Kaspi Shop Health Monitor started.")

    while True:
        try:
            logger.info("Starting health check cycle...")
            async with async_session_factory() as db:
                results = await run_health_check_cycle(db)
                if results:
                    logger.info("Health check cycle completed. Checked %d sellers.", len(results))
                    for r in results:
                        logger.info("  user=%s -> %s", r.get("user_id"), r)
                else:
                    logger.info("No sellers with health monitor enabled.")
        except asyncio.CancelledError:
            logger.info("Health monitor worker cancelled.")
            break
        except Exception as e:
            logger.exception("Error in health monitor loop: %s", e)

        # Check every 15 minutes — cancellation rate and reviews don't change
        # fast enough to need constant polling, and this keeps Kaspi API usage light.
        await asyncio.sleep(900)

def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(health_monitor_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")

if __name__ == "__main__":
    main()

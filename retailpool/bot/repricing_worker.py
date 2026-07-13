"""
Background worker that continuously executes the Kaspi auto-repricing logic.
"""

import asyncio
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import async_session_factory
from retailpool.services.repricing_service import run_repricing_cycle

logger = logging.getLogger(__name__)

async def repricing_loop() -> None:
    """Infinite loop for auto-repricing."""
    logger.info("Kaspi Auto-Repricing Worker started.")
    
    while True:
        try:
            logger.info("Starting repricing cycle...")
            async with async_session_factory() as db:
                results = await run_repricing_cycle(db)
                if results:
                    actions = [r["action"] for r in results]
                    logger.info("Repricing cycle completed. Processed %d rules.", len(results))
                    logger.info("Actions summary: %s", {a: actions.count(a) for a in set(actions)})
                else:
                    logger.info("No active rules to process.")
        except asyncio.CancelledError:
            logger.info("Repricing worker cancelled.")
            break
        except Exception as e:
            logger.exception("Error in repricing loop: %s", e)
            
        # Wait 3 minutes before next check (Kaspi caches pages, no need to spam)
        await asyncio.sleep(180)

def main() -> None:
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(repricing_loop())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")

if __name__ == "__main__":
    main()

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('wenshi.worker')


async def run_worker() -> None:
    logger.info('Wenshi worker started. Mock providers are active.')
    while True:
        await asyncio.sleep(60)
        logger.info('Worker heartbeat: verification cleanup, notification jobs, and order sync placeholders are healthy.')


if __name__ == '__main__':
    asyncio.run(run_worker())

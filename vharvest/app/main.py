import logging
import os
import time
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings
from app.db import init_db
from app.scan_service import needs_initial_scan, start_scan

logger = logging.getLogger(__name__)


def _prepare() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    os.makedirs(settings.poster_dir, exist_ok=True)
    last_error: Exception | None = None
    for _ in range(30):
        try:
            init_db()
            return
        except Exception as exc:
            last_error = exc
            logger.warning("база ещё не готова: %s", exc)
            time.sleep(2)
    if last_error:
        raise last_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    _prepare()
    scheduler = BackgroundScheduler(timezone="Europe/Moscow")
    try:
        trigger = CronTrigger.from_crontab(settings.scan_cron, timezone="Europe/Moscow")
    except ValueError:
        logger.exception("SCAN_CRON не разобран, ночной запуск выключен")
        trigger = None
    if trigger is not None:
        scheduler.add_job(
            start_scan,
            trigger,
            id="nightly-scan",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
    if needs_initial_scan():
        start_scan()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title="vHarvest", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

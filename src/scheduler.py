"""
APScheduler setup for sourcerer v2 proactive digest jobs.

Jobs (all times local to the server):
  - 10:00 daily  → todos digest
  - 11:00 daily  → applications digest

Scheduler is started/stopped by src/bot.py via start() and stop().
Jobs call digest builders directly — no LLM in the loop.
Sends messages via the Telegram Bot API using the shared bot instance.
"""

import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from telegram import Bot

from src.digests import build_applications_digest, build_todos_digest

load_dotenv()

logger = logging.getLogger("sourcerer.scheduler")

TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

_scheduler = AsyncIOScheduler()


## --- Job Functions --- ##


async def _send_todos_digest(bot: Bot) -> None:
    """Build and send the todos digest. Skips silently if nothing to report."""
    try:
        message = build_todos_digest()
        if message is None:
            logger.info("Todos digest: nothing to send")
            return
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="Markdown",
        )
        logger.info("Todos digest sent")
    except Exception as exc:
        logger.error("Todos digest failed: %s", exc)


async def _send_applications_digest(bot: Bot) -> None:
    """Build and send the applications digest. Skips silently if nothing to report."""
    try:
        message = build_applications_digest()
        if message is None:
            logger.info("Applications digest: nothing to send")
            return
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode="Markdown",
        )
        logger.info("Applications digest sent")
    except Exception as exc:
        logger.error("Applications digest failed: %s", exc)


## --- Lifecycle --- ##


def start(bot: Bot) -> None:
    """Register jobs and start the scheduler. Called once from bot.py on startup."""
    _scheduler.add_job(
        _send_todos_digest,
        trigger="cron",
        hour=10,
        minute=0,
        kwargs={"bot": bot},
        id="todos_digest",
        replace_existing=True,
    )
    _scheduler.add_job(
        _send_applications_digest,
        trigger="cron",
        hour=11,
        minute=0,
        kwargs={"bot": bot},
        id="applications_digest",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started (todos@10:00, applications@11:00)")


def stop() -> None:
    """Shut down the scheduler. Called from bot.py on shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
"""
Webhook server using aiohttp — designed for Render.com.

Render keeps the service alive via HTTP health checks,
and Telegram pushes updates via POST to /webhook/<secret>.
"""

import asyncio
import logging

from aiohttp import web
from telegram.ext import Application

from src.config import Config

logger = logging.getLogger(__name__)


async def run_webhook(application: Application, config: Config):
    """Start the PTB webhook + aiohttp web server."""

    # Initialise the bot application
    await application.initialize()
    await application.start()

    # Set webhook on Telegram's side
    webhook_url = config.webhook_url
    logger.info(f"Setting webhook → {webhook_url}")

    await application.bot.set_webhook(
        url=webhook_url,
        secret_token=config.WEBHOOK_SECRET,
        drop_pending_updates=True,
    )

    # Build aiohttp app
    aio_app = web.Application()

    # ── Routes ─────────────────────────────────────────────────────────────────

    async def health(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "bot": "VideoExtractorBot"})

    async def webhook(request: web.Request) -> web.Response:
        secret = request.match_info.get("secret", "")
        if secret != config.WEBHOOK_SECRET:
            logger.warning("Webhook: invalid secret token received.")
            raise web.HTTPForbidden()

        data = await request.json()
        await application.update_queue.put(
            application.bot._build_update(data)  # type: ignore[attr-defined]
        )
        return web.Response(text="OK")

    aio_app.router.add_get("/", health)
    aio_app.router.add_get("/health", health)
    aio_app.router.add_post("/webhook/{secret}", webhook)

    # ── Startup / shutdown hooks ────────────────────────────────────────────────

    async def on_startup(_app):
        logger.info(f"aiohttp server starting on port {config.PORT}")

    async def on_cleanup(_app):
        logger.info("Shutting down bot application…")
        await application.stop()
        await application.shutdown()

    aio_app.on_startup.append(on_startup)
    aio_app.on_cleanup.append(on_cleanup)

    # ── Run ────────────────────────────────────────────────────────────────────
    runner = web.AppRunner(aio_app)
    await runner.setup()

    site = web.TCPSite(runner, host="0.0.0.0", port=config.PORT)
    await site.start()

    logger.info(f"🌐 Webhook server running on port {config.PORT}")
    logger.info(f"🔗 Webhook URL: {webhook_url}")

    # Keep running until cancelled
    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await runner.cleanup()

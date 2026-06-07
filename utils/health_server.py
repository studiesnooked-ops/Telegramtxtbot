"""
Minimal HTTP server for Render health checks.
Keeps Web Service alive while Telegram bot runs in background.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime
import os

logger = logging.getLogger("bot.health")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = json.dumps({
                "status": "ok",
                "service": "telegram-video-bot",
                "time": datetime.utcnow().isoformat() + "Z",
            }).encode()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Disable noisy logs in Render
        return


def run_health_server(port: int = None):
    """
    Starts health server for Render Web Service.
    MUST run in background thread.
    """

    port = port or int(os.environ.get("PORT", 10000))

    server = HTTPServer(("0.0.0.0", port), HealthHandler)

    logger.info("Health server running on http://0.0.0.0:%d", port)

    try:
        server.serve_forever()
    except Exception as e:
        logger.error("Health server crashed: %s", e)
    finally:
        server.server_close()

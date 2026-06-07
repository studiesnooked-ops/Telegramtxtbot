"""
Minimal HTTP server for Render health checks.
Render requires a web service to respond on PORT; this satisfies that.
Runs in a background daemon thread alongside the Telegram webhook.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

logger = logging.getLogger("bot.health")


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health", "/healthz"):
            body = json.dumps({
                "status": "ok",
                "service": "telegram-video-bot",
                "timestamp": datetime.utcnow().isoformat() + "Z",
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
        # Silence default access log spam
        pass


def run_health_server(port: int = 10000):
    """Start the health-check HTTP server (blocking – run in a thread)."""
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info("Health server listening on port %d", port)
    server.serve_forever()

"""Prometheus HTTP server for metrics export (V4.3)"""

import logging
import threading
from http.server import HTTPServer
from prometheus_client import MetricsHandler

logger = logging.getLogger(__name__)


class PrometheusServer:
    """Prometheus metrics HTTP server"""

    def __init__(self, port: int = 8000):
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start metrics server in background thread"""
        self.server = HTTPServer(("", self.port), MetricsHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info(f"Prometheus metrics server started on port {self.port}")

    def stop(self):
        """Stop metrics server"""
        if self.server:
            self.server.shutdown()
            logger.info("Prometheus metrics server stopped")

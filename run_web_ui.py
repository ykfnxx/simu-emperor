#!/usr/bin/env python3
"""
Web UI Launcher for EU4-Style Strategy Game
Usage: python run_web_ui.py
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "ui.web.app:app",
        host="0.0.0.0",
        port=6324,
        reload=True,
        log_level="info"
    )

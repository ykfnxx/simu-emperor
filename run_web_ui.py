#!/usr/bin/env python3
"""
Web UI Launcher for EU4-Style Strategy Game
Usage: uv run eu4-web
"""

import uvicorn


def main():
    """Main entry point for web UI"""
    uvicorn.run(
        "ui.web.app:app",
        host="0.0.0.0",
        port=6324,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    main()

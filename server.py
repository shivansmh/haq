"""Local launcher for the Haq FastAPI backend.

Use environment variables from docs/GMAIL_DEPLOYMENT.md before enabling live Gmail OAuth.
The browser never receives a Google access token; OAuth and token refresh happen in api.main.
"""

from __future__ import annotations

import os

import uvicorn


def run_server() -> None:
    uvicorn.run(
        "api.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    run_server()

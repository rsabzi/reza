"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .assistant import tools as _assistant_tools  # noqa: F401
from .database import create_all
from .modules.personal import models as _personal_models  # noqa: F401
from .modules.personal import routes as personal_routes
from .modules.personal import tools as _personal_tools  # noqa: F401
from .modules.salon import models as _salon_models  # noqa: F401
from .modules.salon import routes as salon_routes
from .modules.salon import tools as _salon_tools  # noqa: F401
from .routes import (
    agent,
    assistant,
    contacts,
    memory,
    outbound,
    scheduler,
    settings,
    steps,
    system,
    tasks,
    tools,
)
from .scheduler import start_scheduler, stop_scheduler
from .tools import builtin as _builtin_tools  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_all()
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


app = FastAPI(title="Agent Core", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https://.*\.e2b\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tasks.router, prefix="/api")
app.include_router(steps.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")
app.include_router(outbound.router, prefix="/api")
app.include_router(scheduler.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(salon_routes.router, prefix="/api")
app.include_router(personal_routes.router, prefix="/api")


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Agent Core"}


# In packaged/local mode, serve the built dashboard and API from one origin.
# The root mount is intentionally registered after every API/docs route.
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if (FRONTEND_DIST / "index.html").is_file():
    app.mount(
        "/",
        StaticFiles(directory=FRONTEND_DIST, html=True),
        name="dashboard",
    )

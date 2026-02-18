"""FastAPI 应用工厂 + main() 入口。"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from simu_emperor.config import GameConfig
from simu_emperor.engine.models.base_data import NationalBaseData
from simu_emperor.game import GameLoop, PhaseError
from simu_emperor.player.schemas import ErrorResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

_WEB_DIR = Path(__file__).parent
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def load_initial_data(data_dir: Path) -> NationalBaseData:
    """从 initial_provinces.json 加载初始全国数据。

    Args:
        data_dir: 数据根目录（包含 initial_provinces.json）

    Returns:
        NationalBaseData 实例（turn=0）
    """
    json_path = data_dir / "initial_provinces.json"
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    raw["turn"] = 0
    return NationalBaseData.model_validate(raw)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """应用生命周期：初始化 DB + GameLoop + Agent 文件系统。"""
    from simu_emperor.agents.llm.providers import MockProvider
    from simu_emperor.engine.models.state import GameState
    from simu_emperor.persistence.database import init_database

    config = GameConfig()
    conn = await init_database(config.db_path)
    provider = MockProvider()
    state = GameState(base_data=load_initial_data(config.data_dir))
    game_loop = GameLoop(state=state, config=config, provider=provider, conn=conn)
    game_loop.initialize_agents()
    app.state.game_loop = game_loop
    yield
    await conn.close()


def create_app(game_loop: GameLoop | None = None) -> FastAPI:
    """创建 FastAPI 应用。

    Args:
        game_loop: 可选的 GameLoop 实例（用于测试注入）。
            如果提供，则跳过 lifespan 自动初始化。
    """
    use_lifespan = game_loop is None
    app = FastAPI(
        title="皇帝模拟器",
        lifespan=lifespan if use_lifespan else None,
    )

    if game_loop is not None:
        app.state.game_loop = game_loop

    # 异常处理
    @app.exception_handler(PhaseError)
    async def phase_error_handler(_request: Request, exc: PhaseError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(error="PhaseError", detail=str(exc)).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error=type(exc).__name__, detail=str(exc)).model_dump(),
        )

    # 路由
    from simu_emperor.player.web.routes.agents import router as agents_router
    from simu_emperor.player.web.routes.game import router as game_router
    from simu_emperor.player.web.routes.reports import router as reports_router

    app.include_router(game_router, prefix="/api")
    app.include_router(agents_router, prefix="/api")
    app.include_router(reports_router, prefix="/api")

    # 静态文件
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # 首页
    @app.get("/")
    async def index(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    return app


def main() -> None:
    """CLI 入口点。"""
    import uvicorn

    uvicorn.run(
        "simu_emperor.player.web.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

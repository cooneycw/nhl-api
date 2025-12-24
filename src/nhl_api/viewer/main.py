"""NHL Data Viewer Backend - FastAPI Application.

Main entry point for the viewer backend service. Provides:
- FastAPI app with lifespan management for database connection
- CORS configuration for frontend integration
- API routing with versioning
- OpenAPI documentation

Usage:
    # Development
    uvicorn nhl_api.viewer.main:app --reload

    # Production
    uvicorn nhl_api.viewer.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from nhl_api.services.db import DatabaseService
from nhl_api.viewer.config import get_settings
from nhl_api.viewer.dependencies import set_db_service
from nhl_api.viewer.routers import (
    coverage,
    dailyfaceoff,
    downloads,
    entities,
    health,
    monitoring,
    quanthockey,
    quick_downloads,
    reconciliation,
    validation,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application lifespan events.

    Handles:
    - Database connection pool initialization on startup
    - Clean shutdown of database connections

    Args:
        app: The FastAPI application instance.

    Yields:
        Control to the application during its lifetime.
    """
    settings = get_settings()

    # Startup
    logger.info("Starting NHL Data Viewer backend...")

    # Initialize database connection
    db = DatabaseService(
        min_connections=settings.db_min_connections,
        max_connections=settings.db_max_connections,
    )

    try:
        await db.connect()
        set_db_service(db)

        # Set start time for uptime tracking
        from nhl_api.viewer.routers.health import set_start_time

        set_start_time(time.time())

        logger.info("Database connection established")

        yield  # Application runs here

    finally:
        # Shutdown
        logger.info("Shutting down NHL Data Viewer backend...")
        set_db_service(None)
        await db.disconnect()
        logger.info("Database connection closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        lifespan=lifespan,
        docs_url=None,  # Custom docs with navbar
        redoc_url=None,  # Custom redoc with navbar
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.cors_allow_methods,
        allow_headers=settings.cors_allow_headers,
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(coverage.router, prefix=f"/api/{settings.api_version}")
    app.include_router(dailyfaceoff.router, prefix=f"/api/{settings.api_version}")
    app.include_router(downloads.router, prefix=f"/api/{settings.api_version}")
    app.include_router(quick_downloads.router, prefix=f"/api/{settings.api_version}")
    app.include_router(quanthockey.router, prefix=f"/api/{settings.api_version}")
    app.include_router(monitoring.router, prefix=f"/api/{settings.api_version}")
    app.include_router(entities.router, prefix=f"/api/{settings.api_version}")
    app.include_router(reconciliation.router, prefix=f"/api/{settings.api_version}")
    app.include_router(validation.router, prefix=f"/api/{settings.api_version}")

    # Favicon endpoint - serve from viewer-frontend/public
    favicon_path = (
        Path(__file__).parent.parent.parent.parent
        / "viewer-frontend"
        / "public"
        / "favicon.svg"
    )

    @app.get("/favicon.svg", include_in_schema=False)
    @app.head("/favicon.svg", include_in_schema=False)
    async def favicon() -> FileResponse:
        """Serve favicon with cache headers."""
        return FileResponse(
            favicon_path,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600, must-revalidate",
            },
        )

    # Also serve as favicon.ico redirect for browsers that request it
    @app.get("/favicon.ico", include_in_schema=False)
    @app.head("/favicon.ico", include_in_schema=False)
    async def favicon_ico() -> FileResponse:
        """Serve favicon (ico redirect)."""
        return FileResponse(
            favicon_path,
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=3600, must-revalidate",
            },
        )

    # Root endpoint - HTML landing page with navbar
    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        """Root endpoint with navigation page."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <title>{settings.api_title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
            min-height: 100vh;
            color: #e2e8f0;
        }}
        nav {{
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding: 0 2rem;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .nav-container {{
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            height: 60px;
            gap: 2rem;
        }}
        .logo {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #60a5fa;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .nav-links {{
            display: flex;
            gap: 0.5rem;
            list-style: none;
        }}
        .nav-links a {{
            color: #94a3b8;
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            transition: all 0.2s;
            font-size: 0.9rem;
        }}
        .nav-links a:hover {{
            background: rgba(96, 165, 250, 0.1);
            color: #60a5fa;
        }}
        .nav-links a.active {{
            background: rgba(96, 165, 250, 0.2);
            color: #60a5fa;
        }}
        main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            color: #f1f5f9;
        }}
        .subtitle {{
            color: #94a3b8;
            margin-bottom: 3rem;
            font-size: 1.1rem;
        }}
        .cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
        }}
        .card {{
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 1.5rem;
            text-decoration: none;
            transition: all 0.3s;
        }}
        .card:hover {{
            transform: translateY(-4px);
            border-color: rgba(96, 165, 250, 0.5);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }}
        .card h3 {{
            color: #60a5fa;
            margin-bottom: 0.5rem;
            font-size: 1.2rem;
        }}
        .card p {{
            color: #94a3b8;
            font-size: 0.9rem;
            line-height: 1.5;
        }}
        .badge {{
            display: inline-block;
            background: rgba(96, 165, 250, 0.2);
            color: #60a5fa;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            margin-top: 1rem;
        }}
        .external {{ color: #a78bfa; }}
        .external .badge {{ background: rgba(167, 139, 250, 0.2); color: #a78bfa; }}
        footer {{
            text-align: center;
            padding: 2rem;
            color: #64748b;
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <nav>
        <div class="nav-container">
            <a href="/" class="logo">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                </svg>
                NHL Data Viewer
            </a>
            <ul class="nav-links">
                <li><a href="/" class="active">Home</a></li>
                <li><a href="/docs">API Docs</a></li>
                <li><a href="/redoc">ReDoc</a></li>
                <li><a href="/health">Health</a></li>
                <li><a href="http://localhost:5173" target="_blank">Frontend ↗</a></li>
            </ul>
        </div>
    </nav>
    <main>
        <h1>{settings.api_title}</h1>
        <p class="subtitle">{settings.api_description} &bull; Version {settings.api_version}</p>
        <div class="cards">
            <a href="/docs" class="card">
                <h3>Swagger UI</h3>
                <p>Interactive API documentation with try-it-out functionality. Test endpoints directly in your browser.</p>
                <span class="badge">OpenAPI 3.0</span>
            </a>
            <a href="/redoc" class="card">
                <h3>ReDoc</h3>
                <p>Clean, readable API reference documentation. Great for sharing with team members.</p>
                <span class="badge">Reference Docs</span>
            </a>
            <a href="/health" class="card">
                <h3>Health Check</h3>
                <p>Monitor service status, database connectivity, and uptime metrics.</p>
                <span class="badge">JSON</span>
            </a>
            <a href="/openapi.json" class="card">
                <h3>OpenAPI Spec</h3>
                <p>Raw OpenAPI specification for code generation and tooling integration.</p>
                <span class="badge">JSON Schema</span>
            </a>
            <a href="http://localhost:5173" target="_blank" class="card external">
                <h3>Frontend Dashboard ↗</h3>
                <p>React-based data viewer with download management, game stats, and player information.</p>
                <span class="badge">Port 5173</span>
            </a>
            <a href="http://localhost:5173/downloads" target="_blank" class="card external">
                <h3>Download Manager ↗</h3>
                <p>Trigger and monitor data downloads from NHL API sources.</p>
                <span class="badge">Port 5173</span>
            </a>
        </div>
    </main>
    <footer>
        NHL Data Viewer Backend &bull; FastAPI {settings.api_version}
    </footer>
</body>
</html>
"""

    # Shared navbar HTML for docs pages
    def get_navbar_html(active_page: str = "") -> str:
        """Generate navbar HTML with active state."""

        def link_class(page: str) -> str:
            return "active" if page == active_page else ""

        return f"""
        <nav style="
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding: 0 2rem;
            position: sticky;
            top: 0;
            z-index: 9999;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        ">
            <div style="
                max-width: 1200px;
                margin: 0 auto;
                display: flex;
                align-items: center;
                height: 60px;
                gap: 2rem;
            ">
                <a href="/" style="
                    font-size: 1.25rem;
                    font-weight: 700;
                    color: #60a5fa;
                    text-decoration: none;
                    display: flex;
                    align-items: center;
                    gap: 0.5rem;
                ">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                    </svg>
                    NHL Data Viewer
                </a>
                <ul style="
                    display: flex;
                    gap: 0.5rem;
                    list-style: none;
                    margin: 0;
                    padding: 0;
                ">
                    <li><a href="/" style="
                        color: {"#60a5fa" if link_class("home") else "#94a3b8"};
                        text-decoration: none;
                        padding: 0.5rem 1rem;
                        border-radius: 6px;
                        font-size: 0.9rem;
                        background: {"rgba(96, 165, 250, 0.2)" if link_class("home") else "transparent"};
                    ">Home</a></li>
                    <li><a href="/docs" style="
                        color: {"#60a5fa" if link_class("docs") else "#94a3b8"};
                        text-decoration: none;
                        padding: 0.5rem 1rem;
                        border-radius: 6px;
                        font-size: 0.9rem;
                        background: {"rgba(96, 165, 250, 0.2)" if link_class("docs") else "transparent"};
                    ">API Docs</a></li>
                    <li><a href="/redoc" style="
                        color: {"#60a5fa" if link_class("redoc") else "#94a3b8"};
                        text-decoration: none;
                        padding: 0.5rem 1rem;
                        border-radius: 6px;
                        font-size: 0.9rem;
                        background: {"rgba(96, 165, 250, 0.2)" if link_class("redoc") else "transparent"};
                    ">ReDoc</a></li>
                    <li><a href="/health" style="
                        color: {"#60a5fa" if link_class("health") else "#94a3b8"};
                        text-decoration: none;
                        padding: 0.5rem 1rem;
                        border-radius: 6px;
                        font-size: 0.9rem;
                        background: {"rgba(96, 165, 250, 0.2)" if link_class("health") else "transparent"};
                    ">Health</a></li>
                    <li><a href="http://localhost:5173" target="_blank" style="
                        color: #94a3b8;
                        text-decoration: none;
                        padding: 0.5rem 1rem;
                        border-radius: 6px;
                        font-size: 0.9rem;
                    ">Frontend ↗</a></li>
                </ul>
            </div>
        </nav>
        """

    # Custom Swagger UI with navbar
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui() -> HTMLResponse:
        """Swagger UI with navigation bar."""
        navbar = get_navbar_html("docs")
        return HTMLResponse(
            f"""
<!DOCTYPE html>
<html>
<head>
    <title>{settings.api_title} - Swagger UI</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body {{ margin: 0; padding: 0; }}
        .swagger-ui .topbar {{ display: none; }}
    </style>
</head>
<body>
    {navbar}
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>
        window.onload = function() {{
            SwaggerUIBundle({{
                url: "/openapi.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout"
            }});
        }};
    </script>
</body>
</html>
"""
        )

    # Custom ReDoc with navbar
    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc() -> HTMLResponse:
        """ReDoc with navigation bar."""
        navbar = get_navbar_html("redoc")
        return HTMLResponse(
            f"""
<!DOCTYPE html>
<html>
<head>
    <title>{settings.api_title} - ReDoc</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
        body {{ margin: 0; padding: 0; }}
    </style>
</head>
<body>
    {navbar}
    <redoc spec-url='/openapi.json'></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
</body>
</html>
"""
        )

    # API info endpoint
    @app.get(f"/api/{settings.api_version}/info")
    async def api_info() -> dict[str, str]:
        """API version and metadata."""
        return {
            "api_version": settings.api_version,
            "title": settings.api_title,
            "description": settings.api_description,
        }

    return app


# Create the app instance
app = create_app()

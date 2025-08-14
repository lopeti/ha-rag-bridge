from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

router = APIRouter(tags=["ui"])

# Get the admin UI build directory
ADMIN_UI_DIR = Path(__file__).parent.parent.parent / "apps" / "admin-ui" / "dist"


# Custom StaticFiles with no-cache headers for CSS/JS
class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        # Add cache control headers to prevent aggressive caching in development
        if response.headers.get("content-type", "").startswith(
            ("text/css", "application/javascript")
        ):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            response.headers["Expires"] = "0"
        return response


# Mount static files if the build directory exists
if ADMIN_UI_DIR.exists():
    router.mount(
        "/admin/ui/assets",
        NoCacheStaticFiles(directory=str(ADMIN_UI_DIR / "assets")),
        name="admin-assets",
    )


@router.get("/admin/ui")
@router.get("/admin/ui/")
@router.get("/admin/ui/{full_path:path}")
async def serve_admin_ui(full_path: str = ""):
    """Serve the admin UI for all /admin/ui routes"""

    # If build directory doesn't exist, return a message
    if not ADMIN_UI_DIR.exists():
        return HTMLResponse(
            """
        <html>
            <head><title>Admin UI Not Built</title></head>
            <body>
                <h1>Admin UI Not Built</h1>
                <p>The admin UI has not been built yet. Please run:</p>
                <pre>cd apps/admin-ui && npm run build</pre>
                <p>Then restart the server.</p>
                <p>Build directory expected at: {}</p>
            </body>
        </html>
        """.format(
                ADMIN_UI_DIR
            )
        )

    # If requesting a specific file that exists, serve it
    if full_path and full_path not in ["", "admin"]:
        file_path = ADMIN_UI_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))

    # For all other routes, serve the index.html (SPA routing)
    index_path = ADMIN_UI_DIR / "index.html"
    if index_path.exists():
        response = FileResponse(str(index_path))
        # Force no-cache for index.html to prevent caching issues
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return HTMLResponse(
        f"""
    <h1>Admin UI Debug</h1>
    <p>ADMIN_UI_DIR: {ADMIN_UI_DIR}</p>
    <p>Exists: {ADMIN_UI_DIR.exists()}</p>
    <p>Index path: {index_path}</p>
    <p>Index exists: {index_path.exists() if ADMIN_UI_DIR.exists() else 'N/A'}</p>
    <p>Full path: '{full_path}'</p>
    """,
        status_code=404,
    )

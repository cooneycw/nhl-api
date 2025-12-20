"""NHL Data Viewer Backend.

FastAPI-based backend for monitoring and exploring NHL data.

Example:
    # Run development server
    uvicorn nhl_api.viewer.main:app --reload

    # Import app for testing
    from nhl_api.viewer import app
"""

from nhl_api.viewer.main import app, create_app

__all__ = ["app", "create_app"]

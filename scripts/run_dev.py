import os
import sys
import uvicorn

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings

if __name__ == "__main__":
    print(f"Starting {settings.PROJECT_NAME} server on http://localhost:8000 ...")
    print("Swagger API documentation available at: http://localhost:8000/docs")
    print("Frontend UI available at: http://localhost:8000/")
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

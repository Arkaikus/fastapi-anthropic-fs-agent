from .core.logging import setup_logging
from .factory import create_app

setup_logging()
app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("agent.main:app", host="0.0.0.0", port=8000, reload=True)

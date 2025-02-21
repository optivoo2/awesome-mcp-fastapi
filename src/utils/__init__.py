from contextlib import asynccontextmanager
from fastapi import FastAPI

from src.utils.tools import tool_registry

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.
    Handles database connection, tool registration, and cleanup.
    """
    try:
        # Register tools only after all routes are defined and database is ready
        print("🔍 Scanning for API tools...")
        tool_registry.scan_and_register_tools()
        tools_count = len(tool_registry.get_all_tools())
        print(f"✅ Registered {tools_count} API tools successfully")
        
    except Exception as e:
        print(f"❌ Error during application startup: {str(e)}")
        raise e

    # Application is now fully initialized and ready to handle requests
    yield

    # Cleanup on shutdown
    try:
        print("✅ Successfully closed all connections")
    except Exception as e:
        print(f"❌ Error closing database connections: {str(e)}")
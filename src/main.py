from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from src.utils import lifespan

# Import the improved tool registry
from src.utils.tools import bind_app_tools, auto_tool

# Create the FastAPI app
app = FastAPI(title="Tool Registry Demo", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Bind app to the tools
# This must be done before defining routes for immediate registration
bind_app_tools(app)

@auto_tool(name="Health Check" ,description="Health Check")
@app.get("/")
async def health_check() -> Dict[str, Any]:
    """Health Check Definition"""
    return {"All Good": "All good"}

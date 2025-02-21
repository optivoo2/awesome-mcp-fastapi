from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from loguru import logger
from src.utils import lifespan

# Import the improved tool registry
from src.utils.tools import create_tool_router, auto_tool, tool_registry

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

# Create the tool router
# This must be done before defining routes for immediate registration
tool_router = create_tool_router(app)

# Define some models
class TextExtractionRequest(BaseModel):
    text: str
    max_tokens: Optional[int] = Field(default=100, description="Maximum number of tokens to extract")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Extract important information from this document.",
                "max_tokens": 50
            }
        }

class ExtractionResult(BaseModel):
    extracted_text: str
    token_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "extracted_text": "Important information from document",
                "token_count": 5
            }
        }

# Define routes with the auto_tool decorator FIRST
@auto_tool(name="health_check", description="Check API health status", tags=["system"])
@app.get("/", response_model=Dict[str, Any])
async def health_check():
    """Check if the API is running correctly"""
    return {"status": "ok", "version": "1.0.0"}

@auto_tool(
    name="text_extractor",
    description="Extract important information from text",
    tags=["extraction", "text"]
)
@app.post("/extract", response_model=ExtractionResult)
async def extract_text(request: TextExtractionRequest) -> ExtractionResult:
    """
    Extracts important information from provided text.
    
    The extractor will analyze the input text and return the most relevant parts
    up to the specified max_tokens limit.
    """
    # Simplified implementation
    words = request.text.split()
    extracted = " ".join(words[:request.max_tokens])
    
    return ExtractionResult(
        extracted_text=extracted,
        token_count=len(extracted.split())
    )

@auto_tool(name="get_document", description="Retrieve a document by ID", tags=["documents"])
@app.get("/document/{doc_id}")
async def get_document(doc_id: str, include_metadata: bool = False) -> Dict[str, Any]:
    """Retrieve a document by its ID with optional metadata"""
    return {
        "id": doc_id,
        "title": f"Document {doc_id}",
        "metadata": {"created": "2023-01-01"} if include_metadata else None
    }

# Example of a non-tool endpoint
@app.get("/internal/stats")
async def internal_stats():
    """Internal endpoint that isn't exposed as a tool"""
    return {"active_users": 100}

# Add a custom endpoint to force re-scan for tools
@app.post("/tools/refresh")
async def refresh_tools():
    """Force a refresh of the tool registry"""
    logger.info("Manual refresh of tool registry requested")
    tool_registry.scan_and_register_tools()
    return {
        "success": True,
        "tools_count": len(tool_registry.get_all_tools())
    }

# Enhanced tools list endpoint
@app.get("/tools/all")
async def get_all_tools():
    """Get the complete list of registered tools"""
    tools = tool_registry.get_all_tools()
    return {
        "tools": tools,
        "count": len(tools),
        "endpoints": [tool.endpoint for tool in tools]
    }
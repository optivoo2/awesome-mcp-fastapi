from fastapi import FastAPI, APIRouter
from pydantic import BaseModel
import inspect
from typing import Dict, List, Any, Optional, Callable, Union
import functools
from loguru import logger

class ToolSchema(BaseModel):
    """Schema for tool metadata"""
    name: str
    description: str
    endpoint: str
    method: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    tags: List[str] = []

class ToolRegistry:
    """Registry to track FastAPI endpoints as tools (implemented as a singleton)"""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            logger.info("Creating new ToolRegistry singleton instance")
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            cls._instance.tools = {}
            cls._instance.app = None
        return cls._instance
    
    def register_tool(self, tool: ToolSchema):
        """Register a new tool"""
        logger.info(f"Registering tool: {tool.name}")
        self.tools[tool.name] = tool
    
    def get_all_tools(self) -> List[ToolSchema]:
        """Get all registered tools"""
        tool_list = list(self.tools.values())
        logger.debug(f"Getting all tools: {len(tool_list)} tools found")
        return tool_list
    
    def set_app(self, app: FastAPI):
        """Set the FastAPI app instance"""
        self.app = app
        logger.info(f"Tool registry connected to FastAPI app: {app.title}")
        
    def scan_and_register_tools(self):
        """Scan routes and register tools"""
        if not self.app:
            logger.error("Cannot scan for tools - app not set")
            return
            
        logger.info("Starting tool scan")
        
        # Clear existing tools to prevent duplicates
        self.tools = {}
        
        # Generate an exhaustive list of all routes
        route_count = 0
        tool_count = 0
        
        for route in self.app.routes:
            route_count += 1
            # Skip tool router's own routes
            if route.path.startswith("/tools") and route.path != "/tools/all":
                continue
                
            # Get the endpoint function
            endpoint_func = route.endpoint
            logger.debug(f"Examining route: {route.path} - {endpoint_func.__name__}")
            
            # Check for _tool_info in all wrappers
            is_tool = False
            tool_info = None
            current_func = endpoint_func
            
            # Unwrap all layers
            while current_func:
                if hasattr(current_func, "_tool_info"):
                    is_tool = True
                    tool_info = current_func._tool_info
                    break
                
                # Move to next wrapper
                next_func = getattr(current_func, "__wrapped__", None)
                if next_func is None or next_func is current_func:
                    break
                current_func = next_func
            
            if is_tool and tool_info:
                tool_count += 1
                logger.info(f"Found tool: {tool_info['name']} at {route.path}")
                
                # Extract input schema
                input_schema = self._extract_input_schema(endpoint_func)
                
                # Extract output schema
                output_schema = self._extract_output_schema(endpoint_func) 
                
                # Get the HTTP method
                method = next(iter(route.methods)) if route.methods else "GET"
                
                # Create and register the tool
                tool = ToolSchema(
                    name=tool_info["name"],
                    description=tool_info["description"],
                    endpoint=route.path,
                    method=method,
                    input_schema=input_schema,
                    output_schema=output_schema,
                    tags=tool_info["tags"]
                )
                
                self.register_tool(tool)
        
        logger.info(f"Tool scan complete. Found {tool_count} tools out of {route_count} routes.")
    
    def _extract_input_schema(self, func) -> Dict[str, Any]:
        """Extract input schema from function parameters"""
        schema = {"type": "object", "properties": {}, "required": []}
        
        try:
            # Unwrap all layers to get to base function
            current_func = func
            while hasattr(current_func, "__wrapped__"):
                current_func = current_func.__wrapped__
            
            # Check for Pydantic model
            sig = inspect.signature(current_func)
            for param_name, param in sig.parameters.items():
                if param.annotation != inspect.Parameter.empty:
                    if hasattr(param.annotation, "model_json_schema"):
                        return param.annotation.model_json_schema()
            
            # Otherwise build from parameters
            for param_name, param in sig.parameters.items():
                # Skip special params
                if param_name in ("self", "cls", "request"):
                    continue
                
                if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                    continue
                
                # Handle types
                param_schema = {"type": "string"}  # Default
                
                if param.annotation != inspect.Parameter.empty:
                    param_schema = self._type_to_schema(param.annotation)
                
                schema["properties"][param_name] = param_schema
                
                # Mark as required if no default
                if param.default == param.empty:
                    schema["required"].append(param_name)
            
            return schema
        except Exception as e:
            logger.error(f"Error extracting input schema: {e}")
            return {"type": "object"}
    
    def _extract_output_schema(self, func) -> Dict[str, Any]:
        """Extract output schema from return type"""
        try:
            # Unwrap all layers
            current_func = func
            while hasattr(current_func, "__wrapped__"):
                current_func = current_func.__wrapped__
            
            sig = inspect.signature(current_func)
            return_type = sig.return_annotation
            
            if return_type == inspect.Signature.empty:
                return {"type": "object"}
            
            if hasattr(return_type, "model_json_schema"):
                return return_type.model_json_schema()
            
            return self._type_to_schema(return_type)
        except Exception as e:
            logger.error(f"Error extracting output schema: {e}")
            return {"type": "object"}
    
    def _type_to_schema(self, type_hint) -> Dict[str, Any]:
        """Convert Python type to JSON schema"""
        basic_types = {
            str: {"type": "string"},
            int: {"type": "integer"},
            float: {"type": "number"},
            bool: {"type": "boolean"},
            list: {"type": "array", "items": {}},
            dict: {"type": "object"},
            None: {"type": "null"}
        }
        
        # Check basic types
        if type_hint in basic_types:
            return basic_types[type_hint]
        
        # Handle generics
        origin = getattr(type_hint, "__origin__", None)
        if origin is not None:
            args = getattr(type_hint, "__args__", [])
            
            # Handle Optional[T] (Union[T, None])
            if origin is Union:
                if len(args) == 2 and args[1] is type(None):
                    base_schema = self._type_to_schema(args[0])
                    if "type" in base_schema:
                        if isinstance(base_schema["type"], str):
                            base_schema["type"] = [base_schema["type"], "null"]
                    return base_schema
            
            # Handle List[T]
            if origin is list or str(origin).endswith("List"):
                if args:
                    return {
                        "type": "array",
                        "items": self._type_to_schema(args[0])
                    }
            
            # Handle Dict
            if origin is dict or str(origin).endswith("Dict"):
                return {"type": "object"}
        
        # Default
        return {"type": "string"}

# Singleton registry
tool_registry = ToolRegistry()

def create_tool_router(app: FastAPI) -> APIRouter:
    """Create a router for tool-related endpoints"""
    # Set the app in the registry
    tool_registry.set_app(app)
    
    # Create the router
    router = APIRouter(prefix="/tools", tags=["tools"])
    
    @router.get("/list", response_model=List[ToolSchema])
    async def list_tools():
        """List all available tools with their schemas"""
        return tool_registry.get_all_tools()
    
    # Register the router with the app
    app.include_router(router)
    
    return router

def auto_tool(name: str, description: Optional[str] = None, tags: List[str] = None):
    """
    Decorator to mark a FastAPI endpoint as a tool.
    
    IMPORTANT: Place this decorator BEFORE the FastAPI route decorator:
    
    @auto_tool("my-tool", "Description")
    @app.get("/path")
    def endpoint():
        ...
    """
    def decorator(func):
        # Store tool info directly on the function
        func._tool_info = {
            "name": name,
            "description": description or func.__doc__ or "",
            "tags": tags or []
        }
        
        logger.info(f"Marked function {func.__name__} as tool: {name}")
        return func
    
    return decorator

# Backwards compatibility
register_as_tool = auto_tool
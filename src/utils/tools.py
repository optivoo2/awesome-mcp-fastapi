from fastapi import FastAPI, APIRouter, Body, Query, Path, Header, Cookie
from fastapi.routing import APIRoute
from pydantic import BaseModel
import inspect
from typing import Dict, List, Any, Optional, Union, get_origin, get_args
from loguru import logger
import json
from datetime import datetime

class ToolSchema(BaseModel):
    """Schema for tool metadata"""

    name: str
    description: str
    endpoint: str
    method: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    tags: List[str] = []
    example_input: Optional[Dict[str, Any]] = None
    example_output: Optional[Any] = None


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

                # Extract input schema based on HTTP method
                method = next(iter(route.methods)) if route.methods else "GET"

                # Different extraction strategies based on HTTP method
                if method.upper() in ["POST", "PUT", "PATCH"]:
                    # For methods with request body
                    input_schema, example_input = self._extract_body_schema(
                        endpoint_func
                    )
                else:
                    # For methods with query/path params
                    input_schema, example_input = self._extract_param_schema(
                        endpoint_func, route
                    )

                # Extract output schema - this is the key improvement
                output_schema, example_output = self._extract_output_schema(
                    endpoint_func
                )

                # Create and register the tool
                tool = ToolSchema(
                    name=tool_info["name"],
                    description=tool_info["description"],
                    endpoint=route.path,
                    method=method,
                    input_schema=input_schema,
                    output_schema=output_schema,
                    tags=tool_info["tags"],
                    example_input=example_input or tool_info.get("example_input"),
                    example_output=example_output or tool_info.get("example_output"),
                )

                self.register_tool(tool)

        logger.info(
            f"Tool scan complete. Found {tool_count} tools out of {route_count} routes."
        )

    def _extract_body_schema(
        self, func
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Extract rich input schema from function parameters with body content"""
        schema = {"type": "object", "properties": {}, "required": []}
        example_input = {}

        try:
            # Unwrap all layers to get to base function
            current_func = func
            while hasattr(current_func, "__wrapped__"):
                current_func = current_func.__wrapped__

            # Get signature
            sig = inspect.signature(current_func)
            
            # Get docstring for additional context
            docstring = inspect.getdoc(current_func)
            if docstring and "description" not in schema:
                # Use first line as description
                schema["description"] = docstring.split("\n")[0]

            # Look for request body parameters
            for param_name, param in sig.parameters.items():
                # Skip special params
                if param_name in ("self", "cls", "request"):
                    continue

                # Skip *args and **kwargs
                if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                    continue

                # Check if parameter uses Body
                if param.default != param.empty and isinstance(
                    param.default, Body.__class__
                ):
                    # This is a Body parameter - could be a Pydantic model or primitive
                    if param.annotation != inspect.Parameter.empty:
                        if hasattr(param.annotation, "model_json_schema"):
                            # Full Pydantic model parameter
                            model_schema = param.annotation.model_json_schema()
                            
                            # Process schema to be more expressive
                            self._enhance_schema_properties(model_schema)
                            
                            # Add model description if available
                            if hasattr(param.annotation, "__doc__") and param.annotation.__doc__:
                                doc = param.annotation.__doc__.strip()
                                if doc:
                                    model_schema["description"] = doc

                            # Try to get examples from model fields
                            if hasattr(param.annotation, "model_fields"):
                                for field_name, field in param.annotation.model_fields.items():
                                    # Extract example for this field
                                    field_example = None
                                    if hasattr(field, "json_schema_extra") and field.json_schema_extra:
                                        if "example" in field.json_schema_extra:
                                            field_example = field.json_schema_extra["example"]
                                    
                                    # Add to overall example
                                    if field_example is not None:
                                        example_input[field_name] = field_example

                            return model_schema, example_input

                    # If we got here, it's a simple Body parameter or Dict
                    # Try to get example from the Body if provided
                    body_params = param.default
                    if hasattr(body_params, "example") and body_params.example:
                        example_input = body_params.example

                    # For dictionaries, provide a more expressive schema
                    return {
                        "type": "object",
                        "additionalProperties": True,
                        "description": f"Request body for {func.__name__}"
                    }, example_input

            # If we got here, look for pydantic models in parameters
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls", "request"):
                    continue

                if param.annotation != inspect.Parameter.empty:
                    if hasattr(param.annotation, "model_json_schema"):
                        # Full Pydantic model parameter
                        model_schema = param.annotation.model_json_schema()
                        
                        # Process schema to be more expressive
                        self._enhance_schema_properties(model_schema)
                        
                        # Add model description if available
                        if hasattr(param.annotation, "__doc__") and param.annotation.__doc__:
                            doc = param.annotation.__doc__.strip()
                            if doc:
                                model_schema["description"] = doc

                        # Try to get examples from model fields
                        if hasattr(param.annotation, "model_fields"):
                            for field_name, field in param.annotation.model_fields.items():
                                # Extract example for this field
                                field_example = None
                                if hasattr(field, "json_schema_extra") and field.json_schema_extra:
                                    if "example" in field.json_schema_extra:
                                        field_example = field.json_schema_extra["example"]
                                
                                # Add to overall example
                                if field_example is not None:
                                    example_input[field_name] = field_example

                        return model_schema, example_input

            # If no body found, return generic object schema with improved description
            return {
                "type": "object", 
                "description": f"Request body for {func.__name__}",
                "additionalProperties": True
            }, example_input

        except Exception as e:
            logger.error(f"Error extracting body schema: {e}")
            return {"type": "object", "description": "Request body"}, None

    def _enhance_schema_properties(self, schema: Dict[str, Any]) -> None:
        """
        Enhance a schema by making properties more expressive
        
        Args:
            schema: The JSON schema to enhance (modified in-place)
        """
        # Process nested properties
        if "properties" in schema:
            for prop_name, prop_schema in schema["properties"].items():
                # Recursively enhance nested properties
                self._enhance_schema_properties(prop_schema)
                
                # Ensure each property has a description
                if "description" not in prop_schema and "title" in prop_schema:
                    prop_schema["description"] = f"{prop_schema['title']} value"
        
        # Process arrays
        if schema.get("type") == "array" and "items" in schema:
            self._enhance_schema_properties(schema["items"])
            
            # Add description for arrays if missing
            if "description" not in schema:
                items_desc = schema["items"].get("description", "items")
                schema["description"] = f"Array of {items_desc}"
        
        # Add description to enums if missing
        if "enum" in schema and "description" not in schema:
            enum_values = ", ".join([str(v) for v in schema["enum"]])
            schema["description"] = f"One of: {enum_values}"
        
        # Add description to objects if missing
        if schema.get("type") == "object" and "description" not in schema and "title" in schema:
            schema["description"] = f"{schema['title']} object"

    def _extract_param_schema(
        self, func, route: APIRoute
    ) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Extract input schema from path and query parameters"""
        schema = {"type": "object", "properties": {}, "required": []}
        example_input = {}

        try:
            # Get path parameters from the route path
            path_params = [
                param[1:-1]
                for param in route.path.split("/")
                if param.startswith("{") and param.endswith("}")
            ]

            # Unwrap all layers to get to base function
            current_func = func
            while hasattr(current_func, "__wrapped__"):
                current_func = current_func.__wrapped__

            # Check signature
            sig = inspect.signature(current_func)

            # Check for Pydantic model parameters first (these could be query objects)
            for param_name, param in sig.parameters.items():
                # Skip special params
                if param_name in ("self", "cls", "request"):
                    continue

                if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                    continue

                # Check if parameter is a Pydantic model
                if param.annotation != inspect.Parameter.empty and hasattr(param.annotation, "model_json_schema"):
                    # This is a Pydantic model for query parameters
                    model_schema = param.annotation.model_json_schema()
                    
                    # Process schema for better descriptions
                    self._enhance_schema_properties(model_schema)
                    
                    # Add model description
                    if hasattr(param.annotation, "__doc__") and param.annotation.__doc__:
                        doc = param.annotation.__doc__.strip()
                        if doc:
                            model_schema["description"] = doc
                    
                    # Get examples from model
                    model_example = {}
                    if hasattr(param.annotation, "model_fields"):
                        for field_name, field in param.annotation.model_fields.items():
                            if hasattr(field, "json_schema_extra") and field.json_schema_extra:
                                if "example" in field.json_schema_extra:
                                    model_example[field_name] = field.json_schema_extra["example"]
                    
                    # Add "in" property for all fields
                    if "properties" in model_schema:
                        for prop_name, prop_schema in model_schema["properties"].items():
                            prop_schema["in"] = "query"
                    
                    # Add model directly to properties instead of wrapping
                    return model_schema, model_example
            
            # If no Pydantic model is found, process individual parameters
            for param_name, param in sig.parameters.items():
                # Skip special params
                if param_name in ("self", "cls", "request"):
                    continue

                if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                    continue

                # Check parameter type (path, query, header, cookie)
                param_in = "query"  # Default is query
                if param_name in path_params:
                    param_in = "path"

                # Check if parameter has explicit location
                if param.default != param.empty:
                    if isinstance(param.default, Path.__class__):
                        param_in = "path"
                    elif isinstance(param.default, Query.__class__):
                        param_in = "query"
                    elif isinstance(param.default, Header.__class__):
                        param_in = "header"
                    elif isinstance(param.default, Cookie.__class__):
                        param_in = "cookie"

                # Get parameter schema
                param_schema = {"type": "string"}  # Default
                example_value = None

                if param.annotation != inspect.Parameter.empty:
                    param_schema, example_value = self._type_to_schema(param.annotation)

                # Get description and example from Field if present
                if param.default != param.empty:
                    if hasattr(param.default, "description"):
                        param_schema["description"] = param.default.description
                    
                    if hasattr(param.default, "example"):
                        example_value = param.default.example
                        
                    # Get default value
                    if hasattr(param.default, "default") and param.default.default != ...:
                        param_schema["default"] = param.default.default

                # Add to schema with parameter location
                schema["properties"][param_name] = {**param_schema, "in": param_in}

                # Add example value
                if example_value is not None:
                    example_input[param_name] = example_value

                # Mark as required if no default value
                if param.default == param.empty or (hasattr(param.default, "default") and param.default.default == ...):
                    schema["required"].append(param_name)

            return schema, example_input

        except Exception as e:
            logger.error(f"Error extracting parameter schema: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"type": "object", "description": "Request parameters"}, None

    def _extract_output_schema(self, func) -> tuple[Dict[str, Any], Optional[Any]]:
        """Extract rich output schema from return type with examples"""
        try:
            # Unwrap all layers to get to base function
            current_func = func
            while hasattr(current_func, "__wrapped__"):
                current_func = current_func.__wrapped__

            sig = inspect.signature(current_func)
            
            # Extract return type annotation
            return_type = sig.return_annotation
            
            # First priority: Look for response_model in route decorator
            response_model = self._extract_response_model(current_func, func)
            
            # Get docstring for description
            doc = inspect.getdoc(current_func)
            doc_description = None
            if doc:
                doc_description = doc.split("\n")[0].strip()
            
            # Determine which model to use for schema generation
            if response_model is not None:
                logger.debug(f"Using response_model from route decorator: {response_model}")
                model_type = response_model
            elif return_type != inspect.Signature.empty:
                logger.debug(f"Using return type annotation: {return_type}")
                model_type = return_type
            else:
                # No type annotation, use a generic object schema with docstring if available
                description = doc_description or "Response object"
                logger.debug(f"No return type information available, using generic schema")
                return {"type": "object", "description": description}, None

            # Handle Dict/Dictionary return types specially
            if model_type is dict or model_type is Dict or get_origin(model_type) is dict:
                # Check if it's a generic Dict or has type arguments
                if get_origin(model_type) is dict and len(get_args(model_type)) == 2:
                    key_type, value_type = get_args(model_type)
                    key_schema, key_example = self._type_to_schema(key_type)
                    value_schema, value_example = self._type_to_schema(value_type)
                    
                    schema = {
                        "type": "object",
                        "additionalProperties": value_schema,
                        "description": doc_description or f"Dictionary with {key_type.__name__} keys and {value_schema.get('description', 'values')}"
                    }
                    
                    # Create an example with the key and value
                    example = {}
                    if key_example is not None and value_example is not None:
                        # Convert key to string (JSON keys must be strings)
                        str_key = str(key_example)
                        example[str_key] = value_example
                    
                    return schema, example
                else:
                    # For plain Dict or Dict without type args, return a generic dictionary schema
                    return {
                        "type": "object", 
                        "description": doc_description or "Dictionary response",
                        "additionalProperties": True
                    }, {"example_key": "example_value"}

            # Handle Pydantic models
            if hasattr(model_type, "model_json_schema"):
                schema = model_type.model_json_schema()
                
                # Process schema to ensure all properties have descriptions
                self._enhance_schema_properties(schema)
                
                # Add description if available
                if "description" not in schema:
                    if doc_description:
                        schema["description"] = doc_description
                    elif "title" in schema:
                        schema["description"] = f"{schema['title']} response"
                
                # Create example output
                example_output = self._create_example_from_model(model_type)
                    
                return schema, example_output
            
            # Handle other return types
            schema, example = self._type_to_schema(model_type)
            
            # Add description from docstring if available
            if "description" not in schema and doc_description:
                schema["description"] = doc_description
                        
            return schema, example
        
        except Exception as e:
            logger.error(f"Error extracting output schema: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"type": "object", "description": "Response data"}, None

    def _extract_response_model(self, current_func, original_func) -> Optional[Any]:
        """Extract response_model from route decorators with multiple strategies"""
        # Strategy 1: Look directly for response_model attribute
        if hasattr(original_func, "response_model"):
            return original_func.response_model
            
        # Strategy 2: Check if function is a FastAPI route with response_model
        if hasattr(original_func, "__closure__") and original_func.__closure__:
            for cell in original_func.__closure__:
                if not hasattr(cell, "cell_contents"):
                    continue
                    
                # Look for response_model in dictionary
                if isinstance(cell.cell_contents, dict) and "response_model" in cell.cell_contents:
                    return cell.cell_contents["response_model"]
                    
                # Look for response_model in APIRouter
                if hasattr(cell.cell_contents, "response_model"):
                    return cell.cell_contents.response_model
        
        # Strategy 3: Check route handler's endpoint
        if hasattr(original_func, "endpoint"):
            if hasattr(original_func.endpoint, "response_model"):
                return original_func.endpoint.response_model
        
        # Strategy 4: Check for router in decorated function
        if hasattr(current_func, "router") and hasattr(current_func.router, "routes"):
            # Try to find matching route
            for route in current_func.router.routes:
                if route.endpoint == current_func:
                    if hasattr(route, "response_model"):
                        return route.response_model
        
        # Strategy 5: Try to find from app routes
        if self.app and hasattr(self.app, "routes"):
            for route in self.app.routes:
                if hasattr(route, "endpoint") and route.endpoint == original_func:
                    if hasattr(route, "response_model"):
                        return route.response_model
        
        # Not found
        return None

    def _create_example_from_model(self, model_type) -> Optional[Dict[str, Any]]:
        """Create an example instance from a Pydantic model"""
        # Try multiple strategies to create an example
        
        # Strategy 1: Use Config.schema_extra.example if available
        if hasattr(model_type, "Config") and hasattr(model_type.Config, "schema_extra"):
            if "example" in model_type.Config.schema_extra:
                return model_type.Config.schema_extra["example"]
        
        # Strategy 2: Build example from field examples
        if hasattr(model_type, "model_fields"):
            field_examples = {}
            for field_name, field in model_type.model_fields.items():
                # Check for example in json_schema_extra
                if hasattr(field, "json_schema_extra") and field.json_schema_extra:
                    if "example" in field.json_schema_extra:
                        field_examples[field_name] = field.json_schema_extra["example"]
                        continue
                
                # If no example provided, generate a placeholder based on field type
                if hasattr(field, "annotation"):
                    field_examples[field_name] = self._generate_field_example(field.annotation)
            
            # Only try to construct if we have field examples            
            if field_examples:
                try:
                    # Try to construct model with examples
                    example_obj = model_type.model_construct(**field_examples)
                    return example_obj.model_dump()
                except Exception as e:
                    logger.debug(f"Could not create example from field examples: {e}")
        
        # Strategy 3: Extract example from docstring
        doc = inspect.getdoc(model_type)
        if doc and "Example:" in doc:
            example_lines = []
            capture = False
            for line in doc.split("\n"):
                if "Example:" in line:
                    capture = True
                    continue
                if capture and line.strip() and not line.startswith(" "):
                    break
                if capture and line.strip():
                    example_lines.append(line)
            
            if example_lines:
                example_str = "\n".join(example_lines)
                try:
                    return json.loads(example_str)
                except json.JSONDecodeError:
                    pass
        
        # Strategy 4: Try to create an instance with default values
        try:
            default_instance = model_type()
            return default_instance.model_dump()
        except Exception:
            pass
            
        # Cannot create example
        return None

    def _generate_field_example(self, annotation) -> Any:
        """Generate a sensible example value based on field type"""
        # Handle basic types
        if annotation is str:
            return "example_string"
        elif annotation is int:
            return 42
        elif annotation is float:
            return 3.14
        elif annotation is bool:
            return True
        elif annotation is list:
            return []
        elif annotation is dict:
            return {}
        elif annotation is datetime:
            return datetime.now().isoformat()
        
        # Handle Optional types
        origin = get_origin(annotation)
        if origin is Union:
            args = get_args(annotation)
            if type(None) in args:
                # Get the non-None type
                non_none_args = [arg for arg in args if arg is not type(None)]
                if non_none_args:
                    return self._generate_field_example(non_none_args[0])
        
        # Handle lists
        if origin is list:
            args = get_args(annotation)
            if args:
                # Create a list with one example item
                item_example = self._generate_field_example(args[0])
                return [item_example]
        
        # Handle enums
        if hasattr(annotation, "__members__") and hasattr(annotation, "__enum__"):
            # Return first enum value
            if annotation.__members__:
                first_key = next(iter(annotation.__members__))
                return first_key
                
        # For Pydantic models, recursively build example
        if hasattr(annotation, "model_fields"):
            try:
                field_examples = {}
                for field_name, field in annotation.model_fields.items():
                    if hasattr(field, "annotation"):
                        field_examples[field_name] = self._generate_field_example(field.annotation)
                
                example_obj = annotation.model_construct(**field_examples)
                return example_obj.model_dump()
            except Exception:
                # Return empty dict if we can't create model instance
                return {}
        
        # Default fallback
        return None

    def _type_to_schema(self, type_hint) -> tuple[Dict[str, Any], Optional[Any]]:
        """Convert Python type to JSON schema with enhanced descriptions and examples"""
        # Enhanced basic types with descriptions
        basic_types = {
            str: ({"type": "string", "description": "Text string"}, "example_string"),
            int: ({"type": "integer", "description": "Integer number"}, 0),
            float: ({"type": "number", "description": "Floating-point number"}, 0.0),
            bool: ({"type": "boolean", "description": "Boolean value"}, False),
            list: ({"type": "array", "items": {}, "description": "List of items"}, []),
            dict: ({"type": "object", "description": "Dictionary of key-value pairs"}, {}),
            None: ({"type": "null", "description": "No value"}, None),
        }

        # Handle None/null explicitly
        if type_hint is None:
            return basic_types[None]

        # Check basic types
        if type_hint in basic_types:
            return basic_types[type_hint]

        # Extract docstring if available for the type
        type_description = None
        if hasattr(type_hint, "__doc__") and type_hint.__doc__:
            doc = type_hint.__doc__.strip()
            if doc:
                type_description = doc.split("\n")[0].strip()

        # Handle Enum types specially
        if hasattr(type_hint, "__members__") and hasattr(type_hint, "__enum__"):
            enum_values = list(type_hint.__members__.keys())
            description = type_description or f"Enumeration with values: {', '.join(enum_values)}"
            return {
                "type": "string", 
                "enum": enum_values,
                "description": description
            }, enum_values[0] if enum_values else None

        # Handle Pydantic models
        if hasattr(type_hint, "model_json_schema"):
            schema = type_hint.model_json_schema()
            
            # Enhance the schema
            self._enhance_schema_properties(schema)
            
            # Add model description if available
            if type_description:
                schema["description"] = type_description

            # Try to create example output
            example_output = None
            try:
                if hasattr(type_hint, "model_construct"):
                    example_obj = type_hint.model_construct()
                    example_output = example_obj.model_dump()
            except Exception as e:
                logger.debug(f"Could not create example output: {e}")
                
            return schema, example_output

        # Handle generics and advanced types
        origin = get_origin(type_hint)
        if origin is not None:
            args = get_args(type_hint)

            # Handle Optional[T] (Union[T, None])
            if origin is Union:
                if type(None) in args:
                    # Find the non-None type
                    non_none_args = [arg for arg in args if arg is not type(None)]
                    if non_none_args:
                        base_schema, example = self._type_to_schema(non_none_args[0])
                        if "type" in base_schema:
                            if isinstance(base_schema["type"], str):
                                base_schema["type"] = [base_schema["type"], "null"]
                                base_schema["description"] = f"Optional {base_schema.get('description', 'value')}"
                        return base_schema, example

                # Handle other Union types
                schemas = []
                for arg in args:
                    schema, _ = self._type_to_schema(arg)
                    schemas.append(schema)

                return {
                    "oneOf": schemas, 
                    "description": "One of multiple possible types"
                }, None

            # Handle List[T]
            if origin is list or str(origin).endswith("List"):
                if args:
                    item_schema, item_example = self._type_to_schema(args[0])
                    schema = {
                        "type": "array", 
                        "items": item_schema,
                        "description": f"List of {item_schema.get('description', 'items')}"
                    }
                    return schema, [item_example] if item_example is not None else []
                
            # Handle Dict[K, V] - Add handling for dictionary types with type arguments
            if origin is dict or str(origin).endswith("Dict"):
                if len(args) >= 2:
                    # Get schemas for key and value types
                    _, key_example = self._type_to_schema(args[0])
                    value_schema, value_example = self._type_to_schema(args[1])
                    
                    # Create schema for dictionary
                    schema = {
                        "type": "object",
                        "additionalProperties": value_schema,
                        "description": f"Dictionary with {args[0].__name__} keys and {value_schema.get('description', 'values')}"
                    }
                    
                    # Create example with the example key and value
                    example = {}
                    if key_example is not None and value_example is not None:
                        # Convert key to string (JSON keys must be strings)
                        str_key = str(key_example)
                        example[str_key] = value_example
                    
                    return schema, example
                
                # Handle Dict with no type arguments
                return basic_types[dict]
        
        # Default fallback - return generic object schema
        logger.debug(f"Using fallback schema for type: {type_hint}")
        return {
            "type": "object",
            "description": f"Object of type {getattr(type_hint, '__name__', str(type_hint))}"
        }, {}

# Singleton registry
tool_registry = ToolRegistry()


def bind_app_tools(app: FastAPI) -> None:
    """Create a router for tool-related endpoints"""
    # Set the app in the registry
    tool_registry.set_app(app)

    # Create a router for tool endpoints
    router = APIRouter(prefix="/tools", tags=["tools"])

    @router.get("/all", response_model=List[ToolSchema])
    async def get_all_tools():
        """Get all registered tools with their schemas"""
        # Scan first to make sure we have all tools
        tool_registry.scan_and_register_tools()
        return tool_registry.get_all_tools()

    @router.get("/scan", response_model=Dict[str, int])
    async def scan_tools():
        """Manually trigger a scan for tools"""
        tool_registry.scan_and_register_tools()
        return {"tools_found": len(tool_registry.get_all_tools())}

    # Register the router with the app
    app.include_router(router)

    # Perform initial scan
    tool_registry.scan_and_register_tools()

    return None


def auto_tool(
    name: str,
    description: Optional[str] = None,
    tags: List[str] = None,
    example_input: Optional[Dict[str, Any]] = None,
    example_output: Optional[Any] = None,
):
    """
    Decorator to mark a FastAPI endpoint as a tool.

    IMPORTANT: Place this decorator BEFORE the FastAPI route decorator:

    @auto_tool("my-tool", "Description")
    @app.get("/path")
    def endpoint():
        ...

    Parameters:
        name: The name of the tool
        description: Description of what the tool does
        tags: List of tags for categorizing the tool
        example_input: Example input parameters
        example_output: Example output
    """

    def decorator(func):
        # Store tool info directly on the function
        func._tool_info = {
            "name": name,
            "description": description or func.__doc__ or "",
            "tags": tags or [],
            "example_input": example_input,
            "example_output": example_output,
        }

        logger.info(f"Marked function {func.__name__} as tool: {name}")
        return func

    return decorator


# Backwards compatibility
register_as_tool = auto_tool


"""
class ImageGenerationInput(BaseModel):
    Input parameters for image generation
    prompt: str = Field(
        ...,
        description="The text prompt to generate an image from",
        example="A serene landscape with mountains and a lake at sunset"
    )
    width: int = Field(
        512,
        description="Width of the generated image in pixels",
        ge=64,
        le=1024,
        example=512
    )
    height: int = Field(
        512,
        description="Height of the generated image in pixels",
        ge=64,
        le=1024,
        example=512
    )
    style: Optional[str] = Field(
        None,
        description="Art style for the image",
        example="photorealistic"
    )

class ImageGenerationOutput(BaseModel):
    Output from image generation
    image_url: str = Field(
        ...,
        description="URL to the generated image",
        example="https://example.com/images/generated_12345.png"
    )
    prompt: str = Field(
        ...,
        description="The prompt that was used",
        example="A serene landscape with mountains and a lake at sunset"
    )
    seed: int = Field(
        ...,
        description="Random seed used for generation",
        example=42
    )

# Example tool with POST request and Pydantic model
@auto_tool(
    name="generate-image",
    description="Generate an image from a text prompt using AI",
    tags=["image", "generation", "creative"]
)
@app.post("/api/images/generate", response_model=ImageGenerationOutput)
async def generate_image(params: ImageGenerationInput):
    Generate an image based on the text prompt and parameters.

    This endpoint uses a diffusion model to create images from text.
    The generation process typically takes 2-5 seconds.

    Example response:
    {
        "image_url": "https://example.com/images/generated_12345.png",
        "prompt": "A serene landscape with mountains and a lake at sunset",
        "seed": 42
    }
    # In a real implementation, this would call an image generation service
    return ImageGenerationOutput(
        image_url=f"https://example.com/images/generated_{hash(params.prompt) % 10000}.png",
        prompt=params.prompt,
        seed=42
    )

# Example with POST request and JSON Body
@auto_tool(
    name="summarize-text",
    description="Summarize a piece of text to a specified length",
    tags=["text", "nlp"]
)
@app.post("/api/text/summarize")
async def summarize_text(
    summarize_request: dict = Body(
        ...,
        example={
            "text": "This is a long text that needs summarizing...",
            "max_length": 50
        }
    )
):
    Summarize the given text to the specified maximum length.

    Example response:
    {
        "summary": "This is a summarized version of the text...",
        "original_length": 150,
        "summary_length": 50
    }
    # Extract parameters from the request body
    text = summarize_request.get("text", "")
    max_length = summarize_request.get("max_length", 100)

    # Simple mock implementation
    words = text.split()
    original_length = len(words)
    summary_length = min(max_length, original_length)
    summary = " ".join(words[:summary_length])

    return {
        "summary": summary,
        "original_length": original_length,
        "summary_length": summary_length
    }

# Tool with dependency injection
def get_current_user():
    # In a real app, this would validate tokens, etc.
    return {"id": 1, "username": "ai_user"}

@auto_tool(
    name="analyze-document",
    description="Analyze the sentiment and key topics in a document",
    tags=["document", "nlp", "analysis"]
)
@app.post("/api/documents/analyze")
async def analyze_document(
    analysis_request: dict = Body(
        ...,
        example={
            "document_id": "doc_12345",
            "include_sentiment": True
        }
    ),
    current_user = Depends(get_current_user)
):
    Analyze a document to extract sentiment and key topics.

    Example response:
    {
        "document_id": "doc_12345",
        "sentiment": "positive",
        "score": 0.87,
        "topics": ["technology", "innovation", "future"],
        "analyzed_by": "ai_user"
    }
    document_id = analysis_request.get("document_id", "unknown")
    include_sentiment = analysis_request.get("include_sentiment", True)

    return {
        "document_id": document_id,
        "sentiment": "positive" if include_sentiment else None,
        "score": 0.87 if include_sentiment else None,
        "topics": ["technology", "innovation", "future"],
        "analyzed_by": current_user["username"]
    }
"""

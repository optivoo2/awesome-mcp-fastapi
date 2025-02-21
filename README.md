# FastAPI Tools Server

A modern, flexible, and scalable framework for building AI-powered tools servers that can be seamlessly integrated with AI applications. This template provides a production-ready foundation for exposing your custom tools, resources, and capabilities to AI systems through a standardized API.

## 🚀 Features

- **Auto-discovery of tools** - Automatically register and expose your tools to AI systems with a simple decorator
- **Strong typing** - Full type checking support with Pydantic models for request/response validation
- **Database integration** - Ready-to-use PostgreSQL and Qdrant vector database connections
- **Scalable architecture** - Modular codebase designed for production workloads
- **Comprehensive documentation** - Each tool is automatically documented with input/output schemas
- **Authentication and security** - Built-in security best practices
- **Docker ready** - Containerization support for easy deployment

## 🔧 Quick Start

```bash
# Clone the repository
git clone https://github.com/MR-GREEN1337/awesome-mcp-fastapi.git
cd awesome-mcp-fastapi

# Set up environment with uv (faster & more reliable)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies with uv
uv sync

# Run the development server
uvicorn src.main:app --reload
```

## 🛠️ Creating a Tool

Creating a new tool is as simple as adding a function with the `@auto_tool` decorator:

```python
from src.utils.tools import auto_tool
from typing import Dict, Any

@auto_tool(
    name="image_captioner", 
    description="Generates a caption for an image", 
    tags=["vision", "media"]
)
async def generate_caption(image_url: str, max_length: int = 50) -> Dict[str, Any]:
    """
    Generate a descriptive caption for the provided image.
    
    Args:
        image_url: URL of the image to caption
        max_length: Maximum caption length in characters
        
    Returns:
        Dictionary containing the caption and confidence score
    """
    # Your implementation here
    return {
        "caption": "A beautiful sunset over the mountains",
        "confidence": 0.92
    }
```

## 📚 Architecture

The project follows a clean, modular architecture:

```
src/
├── api/              # API routes and versioning
│   └── v1/           # Version 1 API endpoints
├── core/             # Core application code
│   └── settings.py   # Application settings
├── db/               # Database connections and models
│   ├── postgresql.py # PostgreSQL connection
│   └── qdrant.py     # Vector database connection
├── utils/            # Utility functions
│   └── tools.py      # Tool registration utilities
└── main.py           # Application entry point
```

## 💪 Built for AI Tools Development

This template is specifically designed for teams building AI-powered tools and capabilities:

- **Developer-first**: Focus on building AI tools, not infrastructure
- **Performance optimized**: Built to handle high-throughput AI workloads
- **AI integration ready**: Pre-configured for common AI service patterns
- **Rapid prototyping**: Go from idea to working AI tool in minutes
- **Tool composition**: Build complex capabilities by combining simpler tools
- **Observability**: Monitor usage, performance, and errors of your AI tools

## 🔍 Why This is Better Than MCP

While the Model Context Protocol (MCP) provides a standardized way for AI applications to access external data and functionality, this template offers several advantages:

1. **Simplified Developer Experience**: No need to learn a new protocol. Use standard FastAPI routes and decorators you're already familiar with.

2. **Broader Compatibility**: Works with any AI system that can make HTTP requests, not just those that implement MCP.

3. **Production-Ready**: Built with production workloads in mind, including database connections, proper error handling, and security best practices.

4. **Flexible Transport**: Not limited to stdio or SSE - can work over HTTP, WebSockets, or any transport you need.

5. **Database Integration**: Built-in connections to PostgreSQL and Qdrant for persistent storage and vector search.

6. **Automatic Schema Validation**: Uses Pydantic for automatic request/response validation without additional boilerplate.

7. **Seamless Authentication**: Built-in support for API keys, OAuth, and other authentication methods.

8. **Technology Stack Freedom**: Not tied to any specific client implementation or technology stack.

9. **Deployment Flexibility**: Can be deployed as a standalone service, part of a larger application, or as a serverless function.

10. **Open Integration**: Easily integrate with existing systems, APIs, and services without protocol constraints.

## 🔐 Environment Variables

Configure your application with the following environment variables (or create a `.env` file):

```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
QDRANT_URL=http://localhost:6333
API_KEY=your_secret_key
DEBUG=True
```

## 🐳 Docker Deployment

```bash
# Build the Docker image (uses uv inside Dockerfile for faster builds)
docker build -t fastapi-tools-server .

# Run the container
docker run -p 8000:8000 --env-file .env fastapi-tools-server
```

Our Dockerfile uses `uv` for dramatically faster builds and dependency resolution:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv for faster dependency installation
RUN pip install uv

# Copy requirements first for better caching
COPY requirements.txt .

# Use uv to install dependencies (much faster than pip)
RUN uv pip install --system -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 📝 Documentation

Once the server is running, visit `http://localhost:8000/docs` to access the interactive API documentation.

## 💡 Example Use Cases

- **Content Generation Tools**: Text summarization, paraphrasing, translation
- **Data Analysis**: Extract insights from datasets, generate statistics
- **Media Processing**: Image captioning, audio transcription, video analysis
- **Knowledge Tools**: Wikipedia searches, data retrieval, fact-checking
- **Productivity Tools**: Email drafting, meeting summarization, task management

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
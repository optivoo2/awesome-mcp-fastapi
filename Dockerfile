FROM python:3.13-slim

ENV PYTHONUNBUFFERED=true
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get -y install --no-install-recommends \
    libpq-dev \
    gcc \
    libcairo2-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy dependency files
COPY pyproject.toml uv.lock .env ./

# Install dependencies using uv
RUN uv pip install --no-cache --system -e .

# Copy application code
COPY src/ ./src/

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000
ENV $(cat .env | xargs)

# Expose the application port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
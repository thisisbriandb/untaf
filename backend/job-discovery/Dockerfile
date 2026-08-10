FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e ".[dev]"

# Copy application code
COPY . .

# Default command (overridden by Procfile on Railway)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[browser]"

# Le worker exécute le repli navigateur du scraper. Sans le binaire Chromium
# et ses dépendances système, ce repli échoue par ImportError au moment où on
# en a besoin — c'est-à-dire quand une API d'ATS ne répond plus.
RUN playwright install --with-deps chromium

# Copy application code
COPY . .

# Default command (overridden by Procfile on Railway)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

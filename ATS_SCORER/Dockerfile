FROM python:3.10-slim

WORKDIR /app

# Install system build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy NLP model
RUN python -m spacy download en_core_web_sm

# Copy source code
COPY . .

# Set Python path to find backend package
ENV PYTHONPATH=/app

# Bind to the PORT environment variable dynamically injected by the host, defaulting to 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

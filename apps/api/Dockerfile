FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install system dependencies (OpenCV, etc.)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies using uv
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Copy source code
COPY . .

# Run FastAPI via Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8888", "--proxy-headers", "--forwarded-allow-ips", "*"]

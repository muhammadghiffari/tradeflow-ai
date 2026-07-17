FROM python:3.13-slim-bookworm

WORKDIR /app

# Fix Debian GPG key rotation, install uv, and system dependencies
RUN pip install uv && \
    apt-get update -o Acquire::AllowInsecureRepositories=true 2>/dev/null; \
    apt-get install -y --allow-unauthenticated debian-archive-keyring 2>/dev/null; \
    apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libmagic1 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies using uv (lockfile ensures deterministic resolution)
COPY pyproject.toml uv.lock ./
ENV UV_HTTP_TIMEOUT=300
ENV UV_REQUEST_RETRIES=10
RUN uv pip install --system -r pyproject.toml

# Copy source code
COPY . .

# Run FastAPI via Uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8888", "--proxy-headers", "--forwarded-allow-ips", "*"]

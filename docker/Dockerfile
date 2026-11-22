# Education Management System - Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install the resolved production environment. The lock is hash-pinned, so
# --require-hashes verifies every artifact against the reviewed SHA-256.
COPY requirements.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Copy application
COPY . .

# The project is not pip-installed in the image, so make the package under src/
# importable for `python -m education_system`. Matches PYTHONPATH in
# deploy/docker-stack.yml and deploy/kubernetes/base/configmap.yaml.
ENV PYTHONPATH=/app/src

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser

# All runtime state lives under var/. Create it here so a named volume mounted
# on /app/var starts out owned by appuser.
RUN mkdir -p var \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health/live')" || exit 1

# Run application (CLI mode)
CMD ["python", "-m", "education_system", "--cli"]

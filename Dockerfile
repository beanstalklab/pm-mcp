FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install `uv` for fast package management
RUN pip install --no-cache-dir uv

# Copy project configuration files first to cache dependencies
COPY pyproject.toml uv.lock* ./

# Install python dependencies
RUN uv sync

# Install Playwright browser and OS-level dependencies for Chromium
RUN uv run playwright install --with-deps chromium

# Copy the rest of the application files
# COPY . /app/

# Supports both stdio (local) and HTTP (multi-user) modes.
# Set MCP_TRANSPORT=streamable-http for multi-user deployment.
EXPOSE 8000

ENV MCP_TRANSPORT=streamable-http
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000

ENTRYPOINT ["uv", "run", "main.py"]

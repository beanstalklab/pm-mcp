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
COPY . /app/

# By default, MCP communicates via standard input/output (stdio)
# We set this entrypoint so a client can execute the container to communicate.
ENTRYPOINT ["uv", "run", "main.py"]

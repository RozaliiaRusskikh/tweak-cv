FROM python:3.13-slim

# WeasyPrint requires these system libs for PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libcairo2 \
    libharfbuzz0b \
    libfontconfig1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies (separate layer for better caching)
COPY pyproject.toml .
RUN uv sync --no-group dev

# Copy source — tweakcv/ contents go to /app so `uvicorn slack_handler:app` resolves correctly
COPY tweakcv/ /app/
COPY harness.json .
COPY base_resume.json .
COPY templates/ ./templates/

RUN mkdir -p /app/data /app/output

EXPOSE 3000

CMD ["uv", "run", "uvicorn", "slack_handler:app", "--host", "0.0.0.0", "--port", "3000"]

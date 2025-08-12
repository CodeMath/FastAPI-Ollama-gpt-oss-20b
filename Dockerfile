# uv-based Python image with Python 3.12
FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

# Preinstall dependencies (allow resolver to update lock)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

# Copy the rest of the app
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Run FastAPI app with uvicorn
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

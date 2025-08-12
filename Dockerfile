# uv-based Python image with Python 3.12
FROM ghcr.io/astral-sh/uv:python3.12-bookworm

WORKDIR /app

# Preinstall dependencies using the lockfile for reproducibility
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Copy the rest of the app
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Run FastAPI app with uvicorn
CMD ["uv", "run", "--frozen", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

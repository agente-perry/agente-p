# Multi-stage build for Cloud Run / Docker.
FROM python:3.11-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
COPY src ./src
RUN uv pip install --system --no-cache .

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src ./src
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
EXPOSE 8080
CMD ["uvicorn", "agenteperry_api.main:app", "--host", "0.0.0.0", "--port", "8080"]

# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Python backend
FROM python:3.12-slim
RUN pip install --no-cache-dir uv awscli
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
# Copy built frontend into the static directory the API serves
COPY --from=frontend-builder /app/src/chrono_architect/static ./src/chrono_architect/static
RUN uv pip install --system --no-cache .
RUN useradd --create-home --uid 10001 chrono && mkdir -p /app/audit-data && chown -R chrono:chrono /app
USER chrono
ENV CHRONO_AUDIT_DIR=/app/audit-data
EXPOSE 8000
CMD ["uvicorn", "chrono_architect.api:app", "--host", "0.0.0.0", "--port", "8000"]

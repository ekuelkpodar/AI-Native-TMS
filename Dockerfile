# Single-service demo image: the FastAPI backend serves the built Vite SPA
# from /frontend-dist (SPA fallback), so the whole product runs as one
# web service with same-origin /api/v1 — no CORS or URL wiring needed.
#
# Build:  docker build -t ai-native-tms .
# Run:    docker run -p 8000:8000 ai-native-tms
#         → http://localhost:8000  (demo login: admin@demo.tms / Demo1234!)
# Render: Blueprint in render.yaml uses this Dockerfile.

FROM node:24-alpine AS web
WORKDIR /srv/web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Same-origin API (backend serves the SPA), so a relative base works everywhere.
ENV VITE_API_URL=/api/v1
RUN npm run build

FROM python:3.12-slim AS api
WORKDIR /srv/app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/seed.py ./seed.py
COPY --from=web /srv/web/dist ./frontend-dist
ENV DATABASE_URL=<redacted> \
    STORAGE_DIR=/srv/app/storage \
    PYTHONUNBUFFERED=1
EXPOSE 8000
# seed.py is idempotent: first boot creates the demo dataset, later boots skip.
CMD sh -c "python seed.py && exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"

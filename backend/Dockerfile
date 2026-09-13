# UNVERIFIED — docker was not installed on the build VM, so this image has
# never been built or run. Provided to complete the docker-compose layout.
FROM python:3.12-slim

WORKDIR /srv/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY seed.py ./seed.py

# SQLite fallback if DATABASE_URL is not provided; compose sets Postgres.
ENV DATABASE_URL=sqlite:///./tms.db \
    STORAGE_DIR=/data/storage

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# StockPulse AI — backend (FastAPI + uvicorn)
# Build context: repository root (~/workspace/stockpulse).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
# psycopg[binary] = Postgres driver (requirements.txt targets SQLite locally;
# production uses DATABASE_URL=postgresql+psycopg://...). Dev tools
# (ruff/black/pytest) ride along harmlessly — keeps one requirements file.
RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && pip install "psycopg[binary]"

COPY backend/ ./

EXPOSE 8000

# $PORT is injected by Render/Heroku-style hosts; defaults to 8000.
# lifespan() runs init_db() on boot, so tables are created automatically.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

FROM python:3.12-slim

WORKDIR /product
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/product/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY tools ./tools

WORKDIR /product/backend
EXPOSE 8000
CMD ["sh", "-lc", "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${EOX_API_WORKERS:-1}"]

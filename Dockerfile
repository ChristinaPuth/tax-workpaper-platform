# One service, one URL: FastAPI serves the API and (from Day 2) the built React app.
# Railway: mount a volume at /app/var so the event log survives redeploys.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY workpaper/ workpaper/
COPY app/ app/
COPY data/ data/

RUN mkdir -p var
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

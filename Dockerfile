# One service, one URL: FastAPI serves the API and the built React app.
# Railway: mount a volume at /app/var so the event log survives redeploys.
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY workpaper/ workpaper/
COPY app/ app/
COPY data/ data/
COPY --from=frontend /frontend/dist frontend/dist

RUN mkdir -p var
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

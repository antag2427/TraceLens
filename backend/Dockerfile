FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 10001 tracelens \
    && mkdir -p /var/lib/tracelens \
    && chown tracelens /var/lib/tracelens
COPY backend/app ./app
COPY data/generated/demo.jsonl /app/data/generated/demo.jsonl
USER tracelens
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

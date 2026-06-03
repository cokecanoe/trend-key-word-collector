FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Data directory for SQLite (overridden by a volume or Railway persistent disk)
RUN mkdir -p /app/data

EXPOSE 5000

CMD ["python", "app/main.py"]

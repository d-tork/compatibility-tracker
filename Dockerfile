# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install production dependencies first (layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/ ./app/
COPY data/ ./data/

# Expose the Flask port
EXPOSE 5000

# Run with the built-in Flask server (replace with gunicorn in production)
CMD ["python", "-m", "app.main"]

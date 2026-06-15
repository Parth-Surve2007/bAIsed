FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables for production
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Expose the port (Cloud Run sets the PORT env var, defaults to 8080)
EXPOSE $PORT

# Run the Flask app with Gunicorn
CMD ["sh", "-c", "gunicorn backend.app:app -b 0.0.0.0:${PORT:-8080} --timeout 120"]

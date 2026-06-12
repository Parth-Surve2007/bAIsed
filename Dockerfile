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

# Expose the port required by Hugging Face Spaces
EXPOSE 7860

# Run the Flask app with Gunicorn
CMD ["gunicorn", "backend.app:app", "-b", "0.0.0.0:7860", "--timeout", "120"]

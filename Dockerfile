# Base image
FROM python:3.11-slim

# Set workdir
WORKDIR /app

# Copy backend files
COPY osint_fastapi_app ./osint_fastapi_app
COPY main.py .
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy React build
COPY osint-frontend/build ./osint-frontend/build

# Expose port for Render
EXPOSE 10000

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]

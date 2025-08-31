FROM python:3.10-slim

WORKDIR /app

COPY osint_fastapi_app/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire folder (important!)
COPY . /app/osint_fastapi_app

CMD ["uvicorn", "osint_fastapi_app.main:app", "--host", "0.0.0.0", "--port", "8000"]

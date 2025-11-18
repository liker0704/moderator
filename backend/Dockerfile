FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY backend/src /app/src

# Environment variables
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]

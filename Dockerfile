# Use Python slim image to reduce base size from ~1GB to ~120MB
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker build cache
COPY requirements.txt /app/

# Upgrade pip and install dependencies without cache
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . /app

# Run server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
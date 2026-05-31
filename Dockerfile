# Use Python image
FROM python:3.10

# Set working directory
WORKDIR /app

# Copy files
COPY . /app

# Install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Run server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
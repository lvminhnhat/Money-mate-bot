# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables to prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if needed (e.g., for certain libraries)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# Use --no-cache-dir to reduce image size
# Also install watchdog for auto-reloading during development
RUN pip install --no-cache-dir -r requirements.txt watchdog

# Copy the credentials directory into the container
# Ensure the service_account.json is correctly placed in the credentials folder locally
COPY ./credentials ./credentials

# Copy the rest of the application code into the container at /app
COPY . .

# Command to run the application using watchmedo for auto-reloading
# This monitors *.py files and restarts the python process on change
CMD ["watchmedo", "auto-restart", "--directory=.", "--pattern=*.py", "--recursive", "--", "python", "main.py"]

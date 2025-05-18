# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# - procps for `ps` and other utilities (psutil might need some underlying tools)
# - util-linux for `dmesg`, `hwclock`, etc.
# - fontconfig (can be removed if not generating images on backend for any other purpose)
RUN apt-get update && \
    apt-get install -y procps util-linux fontconfig && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY ./backend /app/backend
COPY ./frontend /app/frontend

# Expose the port the app runs on
EXPOSE 5000

# Define environment variable
ENV FLASK_APP backend/app.py
ENV FLASK_RUN_HOST 0.0.0.0

# Command to run the application
CMD ["flask", "run"]

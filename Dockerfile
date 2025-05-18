# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# Added radeontop
RUN apt-get update && \
    apt-get install -y procps util-linux fontconfig radeontop && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the new run.py entrypoint script
COPY ./run.py /app/run.py

# Copy the rest of the application code into the container
# Ensure you have an empty backend/__init__.py file locally for 'backend' to be a package
COPY ./backend /app/backend
COPY ./frontend /app/frontend

# Expose the port the app runs on
EXPOSE 5000

# Add /app to PYTHONPATH so 'backend' can be imported as a top-level package
ENV PYTHONPATH=/app
# These ENV vars are now primarily for the custom run.py or if 'flask' commands are used directly.
ENV FLASK_APP=backend.app 
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000
ENV FLASK_DEBUG=0 

# Optional: Set a default polling interval if not provided at runtime
# ENV POLLING_INTERVAL_MS=2000

# Command to run the application via the new entrypoint script
CMD ["python", "run.py"]

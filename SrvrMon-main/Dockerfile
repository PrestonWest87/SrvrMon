# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install system dependencies (including radeontop for AMD GPUs)
RUN apt-get update && \
    apt-get install -y procps util-linux fontconfig radeontop pciutils && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY ./backend /app/backend
COPY ./app.py /app/app.py

# Expose the default Streamlit port
EXPOSE 8501

# Add /app to PYTHONPATH
ENV PYTHONPATH=/app

# Command to run the Streamlit application
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the environment to non-interactive to prevent install errors
ENV DEBIAN_FRONTEND=noninteractive

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed by WeasyPrint
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libgobject-2.0-0 \
    libpangoft2-1.0-0 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy the dependencies file and install Python packages
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Tell the container to listen on the port Render provides
EXPOSE $PORT

# Run the app using gunicorn (Shell form to allow variable substitution)
CMD gunicorn --bind 0.0.0.0:$PORT --log-level debug --access-logfile - --error-logfile - app:app
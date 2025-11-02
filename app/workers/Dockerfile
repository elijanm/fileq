FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    build-essential curl ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workers

# Copy shared requirements from API (keep consistent)
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy worker code
COPY . .

RUN echo "=== Container /workers directory ===" && \
    ls -l && \
    echo "=== Recursive listing ===" && \
    find . -type f

# Default command: run Dramatiq with multiple processes/threads
CMD ["dramatiq", "tasks", "--processes", "2", "--threads", "8"]

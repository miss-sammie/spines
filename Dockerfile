FROM ubuntu:22.04

# Environment setup
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# System dependencies
RUN apt-get update && apt-get install -y \
    # Core system tools
    file less bash coreutils gawk sed grep \
    curl wget \
    # Python and pip
    python3 python3-pip python3-dev \
    # Document processing
    calibre poppler-utils catdoc djvulibre-bin \
    # OCR support
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd \
    # Archive tools
    p7zip-full \
    # Additional dependencies for v2.0
    python3-lxml python3-watchdog \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install production dependencies only
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY static/ ./static/

# Create necessary directories
RUN mkdir -p /app/data /app/books /app/temp /app/logs

# Set up proper permissions for production
RUN chmod -R 755 /app/src && \
    chmod -R 755 /app/static && \
    chmod -R 777 /app/temp && \
    chmod -R 777 /app/logs

# Health check for production
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/api/health || exit 1

# Volume mount points
VOLUME ["/app/books", "/app/data", "/app/logs", "/app/temp"]

# Expose port
EXPOSE 8888

# Run the production application
CMD ["python3", "-m", "src.main"] 
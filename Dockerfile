FROM ubuntu:22.04

# Environment setup
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# System dependencies
RUN apt-get update && apt-get install -y \
    # Core system tools
    file less bash coreutils gawk sed grep \
    curl wget git \
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

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code with new v2.0 structure
COPY src/ ./src/
# Note: static/ is volume mounted for hot reload

# Create necessary directories
RUN mkdir -p /app/data /app/books /app/temp /app/logs

# Set up proper permissions
RUN chmod -R 755 /app/src && \
    chmod -R 777 /app/temp && \
    chmod -R 777 /app/logs

# Health check for v2.0
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/api/health || exit 1

# Volume mount points
VOLUME ["/app/books", "/app/data", "/app/logs"]

# Expose port
EXPOSE 8888

# Run the v2.0 application
CMD ["python3", "-m", "src.main"] 
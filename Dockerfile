FROM ubuntu:22.04

# Set environment variables to avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Core system tools
    file less bash coreutils gawk sed grep \
    curl wget git \
    # Python and pip
    python3 python3-pip python3-dev \
    # Calibre and ebook tools
    calibre \
    # Archive tools
    p7zip-full \
    # OCR support
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd \
    # PDF and document conversion
    poppler-utils catdoc djvulibre-bin \
    # Additional dependencies
    python3-lxml \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY static/ ./static/

# Create data, books, and temp directories
RUN mkdir -p /app/data /app/books /app/temp

# Set up volume mount points
VOLUME ["/app/books", "/app/data"]

# Expose port for web interface
EXPOSE 8888

# Set Python path and default command
ENV PYTHONPATH=/app
CMD ["python3", "/app/src/main.py"] 
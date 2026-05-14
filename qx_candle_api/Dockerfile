FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app/

# Create virtual environment
RUN python -m venv /app/venv

# Activate virtual environment and install dependencies
ENV VIRTUAL_ENV=/app/venv
ENV PATH="/app/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install Playwright
RUN playwright install chromium

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "test.py"]
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright browsers (as root)
RUN pip install playwright
RUN playwright install chromium
RUN playwright install-deps

# Install Python dependencies (as root to avoid permission issues)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Create non-root user with home directory
RUN groupadd -r newsapp && useradd -r -g newsapp -u 1000 -m newsapp

# Create app directory and set ownership
WORKDIR /app
RUN chown -R newsapp:newsapp /app

# Copy application code
COPY --chown=newsapp:newsapp . .

# Create static and config directories
RUN mkdir -p static config && chown -R newsapp:newsapp static config

# Switch to non-root user
USER newsapp

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

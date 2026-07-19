FROM python:3.11-slim

# Install system dependencies for database connection
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /code

# Copy requirements first for caching
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser and its system dependencies
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Set permissions for Hugging Face user (1000)
RUN useradd -m -u 1000 user
RUN chown -R user:user /code
USER user

# Expose Hugging Face default port
EXPOSE 7860

# Run entrypoint script
CMD ["sh", "entrypoint.sh"]

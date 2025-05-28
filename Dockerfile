# Use Python 3.12 slim image
FROM python:3.12-slim

# Install git for submodule support
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Initialize git submodules and create symlink
RUN git submodule update --init --recursive && \
    ln -sf SimpleAgent-Core/SimpleAgent SimpleAgent && \
    ls -la SimpleAgent/

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8080"] 
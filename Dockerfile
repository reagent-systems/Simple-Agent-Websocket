# Use Python 3.12 slim image
FROM python:3.12-slim

# Install git for submodule support
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy the entire project (including .git for submodules)
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Initialize git submodules and create symlink
RUN git config --global --add safe.directory /app && \
    git submodule update --init --recursive && \
    ln -sf SimpleAgent-Core/SimpleAgent SimpleAgent && \
    echo "✅ Submodules initialized successfully" && \
    ls -la SimpleAgent/ && \
    echo "✅ SimpleAgent directory contents:" && \
    ls -la SimpleAgent/core/ || echo "⚠️ Core directory not found"

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8080"] 
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code into container
COPY . .

# Make the start script executable
RUN chmod +x start.sh

# Expose the frontend port for Render.com
EXPOSE 8501

# Boot both the backend and frontend simultaneously
CMD ["./start.sh"]

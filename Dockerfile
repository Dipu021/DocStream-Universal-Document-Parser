FROM python:3.12-slim

# Install Tesseract OCR + dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Expose Render's default port for Docker
EXPOSE 10000

# Run the FastAPI app
# Important: Your main file is inside backend/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
FROM python:3.11-slim

WORKDIR /code

# Install system dependencies
# fonts-noto-cjk 是成绩单 PDF 渲染中文的必需字体，缺了 find_cjk_font 会直接抛错导致导出 500
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

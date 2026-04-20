FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc ca-certificates git \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .

# Install SDK without its strict dep pins to avoid version conflicts
RUN pip install --no-cache-dir --no-deps \
    "neo_api_client @ git+https://github.com/Kotak-Neo/Kotak-neo-api-v2.git@v2.0.1"

# Install our stack (compatible versions, no conflicts)
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

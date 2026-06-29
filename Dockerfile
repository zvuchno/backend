FROM python:3.12
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.prod.txt .
RUN pip install -r requirements.prod.txt --no-cache-dir
COPY . .
CMD [
    "gunicorn",
    "--bind", "0.0.0.0:8000",
    "--forwarded-allow-ips=*",
    "--timeout", "300",
    "config.wsgi"
]

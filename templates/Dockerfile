FROM python:3.12-slim

RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ARG VERSION=dev
ENV APP_VERSION=$VERSION

# APP_PORT and MCP_PORT come from the .env / docker run --env-file
EXPOSE 5101 6101

CMD ["supervisord", "-c", "supervisord.conf"]

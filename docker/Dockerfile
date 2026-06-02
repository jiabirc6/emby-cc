FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir ".[all]"

COPY config.toml /app/config.toml

ENTRYPOINT ["emby-cc"]
CMD ["run", "--config", "/app/config.toml"]

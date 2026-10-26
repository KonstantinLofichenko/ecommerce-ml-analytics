FROM python:3.11.14-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY infra/dbt/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
WORKDIR /workspace/dbt
ENV DBT_PROFILES_DIR=/workspace/dbt
ENTRYPOINT ["dbt"]

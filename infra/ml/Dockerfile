FROM python:3.11.14-slim-bookworm
WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests
RUN pip install --no-cache-dir '.[dev]'
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-c", "import ecommerce_analytics; print('ecommerce_analytics import OK')"]

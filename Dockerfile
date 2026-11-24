FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CONCORDANCE_ROOT=/app

# Pango and fonts: required by WeasyPrint to render PDF reports.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN pip install .

# Samples are optional demo input; runtime data lives in a volume.
COPY samples/native_sample.pdf ./samples/native_sample.pdf
RUN useradd --create-home concordance \
    && mkdir -p /app/data \
    && chown -R concordance /app/data
USER concordance
VOLUME ["/app/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

# Apply migrations, then serve.
CMD ["sh", "-c", "alembic upgrade head && concordance serve --host 0.0.0.0 --port 8000"]

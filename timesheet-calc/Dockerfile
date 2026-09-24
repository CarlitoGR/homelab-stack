# syntax=docker/dockerfile:1

# ---- Build stage: produce the wheel ----
FROM python:3.12-slim AS build
WORKDIR /src
RUN pip install --no-cache-dir build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m build --wheel --outdir /dist

# ---- Runtime stage: wheel + web extra only, non-root ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY --from=build /dist/*.whl /tmp/
RUN pip install "$(ls /tmp/*.whl)[web]" && rm /tmp/*.whl \
    && useradd --create-home --uid 10001 app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/healthz', timeout=2)"
CMD ["timesheet-web", "--host", "0.0.0.0", "--port", "8000"]

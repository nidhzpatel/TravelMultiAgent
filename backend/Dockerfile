FROM python:3.12.7-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY requirements-production.txt .
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip && /opt/venv/bin/pip install -r requirements-production.txt

FROM python:3.12.7-slim
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN groupadd --system voyagemind && useradd --system --gid voyagemind --home /app voyagemind
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY app app
COPY migrations migrations
COPY alembic.ini .
USER voyagemind
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "app.production:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

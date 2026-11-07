FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY common/requirements.txt /tmp/common-requirements.txt
RUN pip install --no-cache-dir -r /tmp/common-requirements.txt

COPY common ./common
COPY fake ./fake

RUN useradd --create-home --uid 10002 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health')"

CMD ["uvicorn", "fake.app:app", "--host", "0.0.0.0", "--port", "8001"]

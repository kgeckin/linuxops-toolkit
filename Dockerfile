FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 LINUXOPS_CONTEXT=container LINUXOPS_DB_PATH=/data/telemetry.db
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . && useradd --create-home --uid 10001 linuxops && mkdir -p /data && chown linuxops:linuxops /data
USER linuxops
EXPOSE 8765
CMD ["uvicorn", "linuxops.service:app", "--host", "0.0.0.0", "--port", "8765"]

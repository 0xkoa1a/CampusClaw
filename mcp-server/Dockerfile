ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv/mcp-server
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./app.py

EXPOSE 8090
USER 10001
CMD ["gunicorn", "--bind", "0.0.0.0:8090", "--workers", "2", "--access-logfile", "-", "app:app"]

ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY scripts ./scripts
COPY wsgi.py ./wsgi.py
RUN mkdir -p /app/data /app/uploads && chown -R 10001:10001 /app
USER 10001
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "wsgi:app"]

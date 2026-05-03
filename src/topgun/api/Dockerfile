FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends redis-server && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY src/topgun/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml /topgun/pyproject.toml
COPY src/ /topgun/src/
RUN pip install --no-cache-dir /topgun

COPY src/topgun/api/main.py .
COPY src/topgun/api/entrypoint.sh .
RUN chmod +x entrypoint.sh
CMD ["./entrypoint.sh"]

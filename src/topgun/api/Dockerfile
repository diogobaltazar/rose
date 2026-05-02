FROM python:3.12-slim
WORKDIR /app
COPY src/topgun/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml /topgun/pyproject.toml
COPY src/ /topgun/src/
RUN pip install --no-cache-dir /topgun

COPY src/topgun/api/main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.11-slim
WORKDIR /app
COPY services/api/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/api /app/services/api
COPY packages /app/packages
COPY apps /app/apps
CMD ["uvicorn", "services.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

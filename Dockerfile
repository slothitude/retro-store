FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 5555
CMD ["gunicorn", "--bind", "0.0.0.0:5555", "--workers", "2", "--threads", "4", "app:create_app()"]

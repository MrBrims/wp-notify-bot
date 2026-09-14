FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY tests ./tests
COPY pytest.ini ./pytest.ini

ENV PYTHONPATH=/app/src
ENV DATABASE_PATH=/app/data/bot.db

RUN mkdir -p /app/data

CMD ["python", "-m", "wp_notify_bot"]

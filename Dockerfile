FROM python:3.11-alpine

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scraper.py llm.py email_sender.py main.py ./

USER appuser

ENTRYPOINT ["python", "main.py"]

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /srv

# Dependencies first so source edits don't invalidate the install layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY landing.html form.html thanks.html dashboard.html styles.css app.js ./

RUN useradd --create-home --uid 1000 blinkdrop
USER blinkdrop

# Shell form so Cloud Run's injected $PORT expands.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}

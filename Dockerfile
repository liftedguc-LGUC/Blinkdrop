# Pin by digest so a rebuild ships the base you reviewed. Update deliberately:
#   docker pull python:3.11-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim
FROM python:3.11-slim@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534

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

# Shell form so Cloud Run's injected $PORT expands. --proxy-headers makes the
# real client address available for logging and rate limiting instead of the
# front end's.
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} \
    --proxy-headers --forwarded-allow-ips='*'

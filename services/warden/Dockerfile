FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin warden
WORKDIR /app
COPY services/warden/ /app/
RUN python -m pip install --no-cache-dir '.[postgres]'

USER warden
EXPOSE 8080
CMD ["uvicorn", "warden_service.app:app", "--host", "0.0.0.0", "--port", "8080"]

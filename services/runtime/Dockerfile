FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 runtime
WORKDIR /app
COPY services/runtime /app
RUN pip install --no-cache-dir '.[postgres]'
USER runtime
EXPOSE 8082
CMD ["genesis-runtime-manager"]

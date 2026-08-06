FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 controltower
WORKDIR /app
COPY services/control-tower /app
RUN pip install --no-cache-dir '.[postgres]'
USER controltower
EXPOSE 8084
CMD ["genesis-control-tower"]

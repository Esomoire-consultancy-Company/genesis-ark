# Package and bundled browser versions must match.
FROM mcr.microsoft.com/playwright/python:v1.61.0-noble

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    CLOUDBROWSER_EXECUTOR_MODE=PLAYWRIGHT \
    CLOUDBROWSER_QUARANTINE_ROOT=/home/pwuser/quarantine

WORKDIR /home/pwuser/app
COPY --chown=pwuser:pwuser services/cloudbrowser/ /home/pwuser/app/
RUN python -m pip install --no-cache-dir '.[production]' \
    && install -d -m 0700 -o pwuser -g pwuser /home/pwuser/quarantine

USER pwuser
EXPOSE 8081
CMD ["uvicorn", "cloudbrowser_service.app:app", "--host", "0.0.0.0", "--port", "8081"]

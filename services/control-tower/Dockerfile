FROM python:3.13-slim
RUN useradd --create-home --uid 10001 controltower
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
USER 10001
EXPOSE 8080
ENTRYPOINT ["genesis-control-tower"]

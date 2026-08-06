FROM python:3.13-slim
RUN groupadd --system genesis && useradd --system --gid genesis --create-home genesis
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
USER genesis
EXPOSE 8080
ENTRYPOINT ["genesis-edge-node"]

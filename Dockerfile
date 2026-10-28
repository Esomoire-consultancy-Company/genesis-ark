# Dedicated staging-only static Gateway container. No app runtime or secrets.
FROM nginx:1.28-alpine
COPY gateway/nginx.conf /etc/nginx/conf.d/default.conf
COPY gateway/index.html gateway/portal.js gateway/styles.css gateway/favicon.svg /usr/share/nginx/html/
EXPOSE 8080

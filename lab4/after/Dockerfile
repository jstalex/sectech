# Сборка зависимостей отдельно от среды исполнения.
FROM alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f AS build
RUN apk add --no-cache python3 py3-pip
COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --target=/opt/python -r /tmp/requirements.txt

# Исправлено: минимальный базовый образ закреплён digest.
FROM alpine:3.22@sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f
# Исправлено: в финальном образе только Python и зависимости приложения.
RUN apk add --no-cache python3 \
    && addgroup -g 10001 app \
    && adduser -D -H -u 10001 -G app app
ENV PYTHONPATH=/opt/python PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=build /opt/python /opt/python
WORKDIR /app
COPY app/app.py .
# Исправлено: непривилегированный пользователь.
USER app
# Исправлено: оставлен только порт приложения.
EXPOSE 5000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=2)"]
CMD ["python3", "app.py"]

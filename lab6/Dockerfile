FROM python:3.13-alpine
RUN apk add --no-cache curl bind-tools postgresql-client
COPY api.py /app/api.py
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["python", "/app/api.py"]

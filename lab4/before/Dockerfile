FROM ubuntu:20.04
USER root
RUN apt-get update && apt-get install -y \
    python3 python3-pip curl wget \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/ .
RUN pip3 install --no-cache-dir -r requirements.txt
EXPOSE 5000 22
CMD ["python3", "app.py"]

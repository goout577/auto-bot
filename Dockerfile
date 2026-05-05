FROM docker.m.daocloud.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --retries 10 --timeout 120 -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com -r requirements.txt

COPY . .

RUN mkdir -p data logs

EXPOSE 8501

CMD ["python", "loop.py"]

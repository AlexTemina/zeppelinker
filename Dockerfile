# syntax=docker/dockerfile:1

FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py bot.py botext.py commands.py config.py urlutils.py ./
COPY fixers ./fixers
COPY hltb ./hltb

USER nobody
CMD ["python", "main.py"]

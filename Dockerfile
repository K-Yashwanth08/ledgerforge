FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv/ledgerforge

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 ledgerforge \
    && useradd --system --uid 10001 --gid ledgerforge --home-dir /srv/ledgerforge ledgerforge

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && pip install -r requirements.txt
COPY --chown=ledgerforge:ledgerforge . .

USER ledgerforge
EXPOSE 8000
CMD ["python", "-m", "scripts.container_start"]

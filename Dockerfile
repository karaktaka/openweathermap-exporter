# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:latest AS uv
FROM alpine AS base

# Setup env
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1

COPY --from=uv /uv /usr/local/bin/

ARG UID=10001
RUN adduser -D -H -h /app -u "${UID}" appuser

USER appuser
WORKDIR /app

COPY --chown=${UID} exporter/client.py exporter/client.py.lock /app/
COPY --chown=${UID} exporter/config.yaml.template /app/config.yaml
RUN --mount=type=cache,uid=${UID},target=/app/.cache \
    uv sync --frozen --script client.py

CMD [ "uv", "run", "--script" ,"client.py" ]

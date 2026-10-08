FROM python:3.12-slim

RUN pip install --no-cache-dir uv

# non-root user + writable dirs (/uv-cache is shared across runs via a named volume)
RUN useradd -m -u 1000 sandbox \
 && mkdir -p /workspace /uv-cache \
 && chown sandbox /workspace \
 && chmod 777 /uv-cache

ENV UV_CACHE_DIR=/uv-cache \
    UV_PYTHON=/usr/local/bin/python \
    UV_PYTHON_DOWNLOADS=never \
    HOME=/tmp \
    MPLCONFIGDIR=/tmp/mpl

USER sandbox
WORKDIR /workspace

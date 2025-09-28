# =========================================
# Stage 1: Builder (build wheels/venv)
# =========================================
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# toolchain & headers để build các gói có C-extension (psycopg2, Pillow, cryptography…)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git curl && \
    rm -rf /var/lib/apt/lists/*

# venv riêng tại /opt/venv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# chỉ copy requirements để tối ưu cache
COPY requirements.txt requirements.dev.txt /tmp/
RUN pip install --no-binary=:all: psycopg2==2.9.9


# cài dependencies (prod + optional dev)
ARG DEV=false
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements.txt && \
    if [ "$DEV" = "true" ]; then pip install -r /tmp/requirements.dev.txt; fi && \
    rm -rf /root/.cache /tmp/*


# =========================================
# Stage 2: Production runtime
# =========================================
FROM python:3.12-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:/scripts:$PATH" \
    DJANGO_SETTINGS_MODULE=app.settings

# chỉ cài runtime libs tối thiểu
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 libjpeg62-turbo zlib1g tzdata curl bash git && \
    rm -rf /var/lib/apt/lists/*

# user không phải root
RUN addgroup --system django && adduser --system --ingroup django django

# thư mục ứng dụng & volumes
RUN mkdir -p /app /vol/web/static /vol/web/media /vol/web/logs && \
    chown -R django:django /app /vol && \
    chmod -R 755 /vol

# nhận venv đã build
COPY --from=builder /opt/venv /opt/venv

# copy scripts trước (để giữ cache tốt hơn)
COPY --chown=django:django ./scripts /scripts
RUN chmod -R +x /scripts

# copy mã nguồn
COPY --chown=django:django ./app /app

WORKDIR /app
EXPOSE 8000
USER django

# healthcheck (cần /health/ trên Django)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:8000/health/ || exit 1

# lệnh mặc định (run.sh sẽ chọn gunicorn/runserver theo DEBUG)
CMD ["run.sh"]


# =========================================
# Stage 3: Development runtime (tùy chọn)
# =========================================
FROM production AS development

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    vim nano htop jq tree && \
    rm -rf /var/lib/apt/lists/*
USER django

CMD ["run-dev.sh"]

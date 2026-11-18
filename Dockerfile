# syntax=docker/dockerfile:1
# Raphael core: agent webhooks + dispatch orchestrator in one process (run.py).
# Ignis runs separately (user-side) and polls this service outbound.
#
#   docker build -t raphael-core .
#   docker run -p 8091:8091 -v raphael-data:/data raphael-core

FROM python:3.12-slim AS build
# Large wheels (scipy, scikit-learn) on slow links: wait longer and retry.
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_DEFAULT_TIMEOUT=60 PIP_RETRIES=10
WORKDIR /src
RUN python -m venv /opt/venv
COPY requirements-bootstrap.txt ./
RUN /opt/venv/bin/python -m pip install --require-hashes -r requirements-bootstrap.txt
COPY contracts ./contracts
COPY agent ./agent
COPY dispatch ./dispatch
# Install third-party dependencies only. Core still reads repo-relative files
# (contracts/, CONTRACTS_VERSION, reply templates, fixtures), so it runs from
# the source tree copied into /app below; run.py puts agent/ and dispatch/
# first on sys.path.
RUN /opt/venv/bin/python -m pip install ./agent ./dispatch \
    && /opt/venv/bin/python -m pip uninstall -y raphael-agent raphael-dispatch

FROM python:3.12-slim
RUN useradd --system --uid 10001 --home-dir /data --shell /usr/sbin/nologin raphael \
    && mkdir -p /data && chown raphael:raphael /data
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY run.py CONTRACTS_VERSION ./
COPY contracts ./contracts
COPY agent ./agent
COPY dispatch ./dispatch
COPY interface/github-native/templates ./interface/github-native/templates
# Safe defaults: listen on all interfaces inside the container, keep state on
# the /data volume, never publish to GitHub and keep local ML off (v1 scope).
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    RAPHAEL_AGENT_LISTEN=0.0.0.0:8091 \
    RAPHAEL_AGENT_DATA_DIR=/data \
    RAPHAEL_MODEL_ENABLED=0 \
    RAPHAEL_PARTNER_MODE=dry_run \
    RAPHAEL_PUBLISH_MODE=dry_run
USER raphael
WORKDIR /data
VOLUME ["/data"]
EXPOSE 8091
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8091/health', timeout=4)"]
CMD ["python", "/app/run.py"]

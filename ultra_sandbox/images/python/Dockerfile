# ultra-sandbox/python
FROM python:3.12-slim-bookworm
# ultra-sandbox: ensure git is available for clones + git-based dependencies
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates) || true
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PATH="/home/sandbox/.local/bin:$PATH"
RUN pip install --user -q pytest
WORKDIR /work

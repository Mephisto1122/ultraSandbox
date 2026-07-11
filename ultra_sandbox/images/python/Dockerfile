# ultra-sandbox/python
FROM python:3.12-slim-bookworm
# ultra-sandbox: ensure git is available for clones + git-based dependencies
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates) || true
# Test runner installed SYSTEM-WIDE (not --user): the sandbox runs with
# HOME=/work/.home, so anything under /home/sandbox/.local would be invisible at
# runtime. System-wide means `pytest` works offline, with no network needed.
RUN pip install --no-cache-dir -q pytest pytest-timeout
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /work

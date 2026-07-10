# ultra-sandbox/lua
FROM nickblah/lua:5.4
# ultra-sandbox: ensure git is available for clones + git-based dependencies
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates) || true
USER root
RUN (command -v useradd && useradd -m sandbox) || adduser -D sandbox || true
RUN mkdir -p /work && chown sandbox /work || mkdir -p /work
USER sandbox
WORKDIR /work

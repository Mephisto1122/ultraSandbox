# ultra-sandbox/lua
FROM nickblah/lua:5.4
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates lua5.4 luarocks && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates luarocks) || true
# busted = the standard Lua test runner; system-wide so it survives the HOME override
RUN luarocks install busted 2>/dev/null || true
RUN (command -v useradd >/dev/null 2>&1 && useradd -m sandbox) || adduser -D sandbox || true
RUN mkdir -p /work && chown sandbox /work 2>/dev/null || mkdir -p /work
USER sandbox
WORKDIR /work

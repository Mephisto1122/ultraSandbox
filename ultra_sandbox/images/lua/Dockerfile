# ultra-sandbox/lua
FROM nickblah/lua:5.4
USER root
RUN (command -v useradd && useradd -m sandbox) || adduser -D sandbox || true
RUN mkdir -p /work && chown sandbox /work || mkdir -p /work
USER sandbox
WORKDIR /work

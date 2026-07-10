# ultra-sandbox/crystal
FROM crystallang/crystal:latest-alpine
RUN adduser -D sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
WORKDIR /work

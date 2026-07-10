# ultra-sandbox/zig
FROM alpine:3.20
# ultra-sandbox: ensure git is available for clones + git-based dependencies
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates) || true
RUN apk add --no-cache curl xz && \
    curl -sSL https://ziglang.org/download/0.13.0/zig-linux-x86_64-0.13.0.tar.xz -o /tmp/z.tar.xz && \
    mkdir -p /opt/zig && tar -xJf /tmp/z.tar.xz -C /opt/zig --strip-components=1 && rm /tmp/z.tar.xz && \
    adduser -D sandbox && mkdir -p /work && chown sandbox /work
ENV PATH="/opt/zig:${PATH}"
USER sandbox
WORKDIR /work

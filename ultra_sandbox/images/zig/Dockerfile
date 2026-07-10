# ultra-sandbox/zig
FROM alpine:3.20
RUN apk add --no-cache curl xz && \
    curl -sSL https://ziglang.org/download/0.13.0/zig-linux-x86_64-0.13.0.tar.xz -o /tmp/z.tar.xz && \
    mkdir -p /opt/zig && tar -xJf /tmp/z.tar.xz -C /opt/zig --strip-components=1 && rm /tmp/z.tar.xz && \
    adduser -D sandbox && mkdir -p /work && chown sandbox /work
ENV PATH="/opt/zig:${PATH}"
USER sandbox
WORKDIR /work

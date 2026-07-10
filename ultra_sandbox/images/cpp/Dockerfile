# ultra-sandbox/cpp - gcc + clang + cmake + ctest
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang cmake ninja-build git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
WORKDIR /work

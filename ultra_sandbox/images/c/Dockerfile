# ultra-sandbox/c
FROM gcc:13-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
WORKDIR /work

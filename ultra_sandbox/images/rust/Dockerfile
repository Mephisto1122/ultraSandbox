# ultra-sandbox/rust
FROM rust:1.84-slim-bookworm
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
ENV CARGO_HOME=/home/sandbox/.cargo
WORKDIR /work

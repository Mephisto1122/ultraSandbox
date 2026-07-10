# ultra-sandbox/ruby
FROM ruby:3.3-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
WORKDIR /work

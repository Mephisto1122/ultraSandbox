# ultra-sandbox/elixir
FROM elixir:1.17-slim
RUN mix local.hex --force && mix local.rebar --force
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
WORKDIR /work

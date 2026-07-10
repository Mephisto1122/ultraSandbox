# ultra-sandbox/dotnet
FROM mcr.microsoft.com/dotnet/sdk:8.0
# ultra-sandbox: ensure git is available for clones + git-based dependencies
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates) || true
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
WORKDIR /work

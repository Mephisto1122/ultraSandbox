# ultra-sandbox/dotnet
FROM mcr.microsoft.com/dotnet/sdk:8.0
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
WORKDIR /work

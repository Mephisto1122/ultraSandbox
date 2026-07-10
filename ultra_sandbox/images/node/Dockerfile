# ultra-sandbox/node
FROM node:22-bookworm-slim
# ultra-sandbox: ensure git is available for clones + git-based dependencies
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates) || true
RUN mkdir -p /work && chown node:node /work
USER node
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
WORKDIR /work

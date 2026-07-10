# ultra-sandbox/typescript
FROM node:22-bookworm-slim
RUN npm install -g typescript >/dev/null 2>&1
RUN mkdir -p /work && chown node:node /work
USER node
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
WORKDIR /work

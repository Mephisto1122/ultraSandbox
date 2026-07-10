# ultra-sandbox/scala
FROM sbtscala/scala-sbt:eclipse-temurin-21.0.2_13_1.9.9_3.4.0
# ultra-sandbox: ensure git is available for clones + git-based dependencies
USER root
RUN (command -v apt-get >/dev/null 2>&1 && apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*) || (command -v apk >/dev/null 2>&1 && apk add --no-cache git ca-certificates) || true
RUN mkdir -p /work
WORKDIR /work

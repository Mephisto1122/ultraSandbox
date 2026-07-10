# ultra-sandbox/kotlin
FROM gradle:8-jdk21
USER root
RUN apt-get update && apt-get install -y --no-install-recommends unzip curl \
    && curl -sSL https://github.com/JetBrains/kotlin/releases/download/v2.0.0/kotlin-compiler-2.0.0.zip -o /tmp/k.zip \
    && unzip -q /tmp/k.zip -d /opt && rm /tmp/k.zip \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/opt/kotlinc/bin:${PATH}"
RUN mkdir -p /work && chown gradle /work
USER gradle
WORKDIR /work

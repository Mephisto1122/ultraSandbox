# ultra-sandbox/php  (php-cli + composer + phpunit)
FROM php:8.3-cli-bookworm
COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
RUN apt-get update && apt-get install -y --no-install-recommends git unzip \
    && rm -rf /var/lib/apt/lists/*
RUN useradd -m sandbox && mkdir -p /work && chown sandbox /work
USER sandbox
WORKDIR /work

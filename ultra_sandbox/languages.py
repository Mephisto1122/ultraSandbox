"""Single source of truth for every supported language.

Before this existed, the set of languages lived in two places (models.DOCKER_LANGS
and the command dicts in docker_driver) and could silently drift — a language
could be *accepted* by create_sandbox but have no build command. Now everything
derives from LANGUAGES, and a consistency test asserts each entry has a matching
Dockerfile.

Each Spec carries the toolchain's native commands. `${target}` / `${filter}` are
substituted (already shlex-quoted) by the driver; absent placeholders mean the
argument isn't supported for that language.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Spec:
    driver: str            # "docker" | "mac"
    build: str             # native build command (shell, run inside the sandbox)
    test: str              # native test command
    test_filter: str = ""  # test command with a {filter} placeholder; "" = unsupported
    dep_add: str = ""      # command to add deps, with {deps} placeholder; "" = unsupported
    network_build: bool = False  # standard build fetches deps from the network
    image: str = ""        # base image (documentation; the Dockerfile is authoritative)


LANGUAGES: dict[str, Spec] = {
    # ---- compiled, self-contained (build works offline) ----
    "go": Spec(
        driver="docker",
        build="go build ./...",
        test="go test ./...",
        test_filter="go test ./... -run {filter}",
        dep_add="go get {deps}",
        image="golang:1.24-bookworm",
    ),
    "c": Spec(
        driver="docker",
        build="if [ -f CMakeLists.txt ]; then cmake -S . -B build && cmake --build build -j; "
              "else cc -Wall -Wextra $(find . -name '*.c') -o build_out; fi",
        test="if [ -d build ]; then ctest --test-dir build --output-on-failure; "
             "else ./build_out; fi",
        image="gcc:13-bookworm",
    ),
    "cpp": Spec(
        driver="docker",
        build="cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug && cmake --build build -j",
        test="ctest --test-dir build --output-on-failure",
        test_filter="ctest --test-dir build --output-on-failure -R {filter}",
        image="gcc:13-bookworm",
    ),
    "rust": Spec(
        driver="docker",
        build="cargo build",
        test="cargo test",
        test_filter="cargo test {filter}",
        dep_add="cargo add {deps}",
        network_build=True,
        image="rust:1.84-slim-bookworm",
    ),
    "zig": Spec(
        driver="docker",
        build="if [ -f build.zig ]; then zig build; "
              "else zig build-exe $(find . -name '*.zig' | head -1); fi",
        test="if [ -f build.zig ]; then zig build test; "
             "else zig test $(find . -name '*.zig' | head -1); fi",
        image="alpine:3.20",  # zig installed in the Dockerfile
    ),
    "haskell": Spec(
        driver="docker",
        build="if [ -f *.cabal ] || ls ./*.cabal >/dev/null 2>&1; then cabal build; "
              "else ghc --make $(find . -name '*.hs' | head -1) -o build_out; fi",
        test="if ls ./*.cabal >/dev/null 2>&1; then cabal test; else ./build_out; fi",
        network_build=True,
        image="haskell:9.8-slim",
    ),
    "crystal": Spec(
        driver="docker",
        build="crystal build $(find . -name '*.cr' ! -path '*/spec/*' | head -1) -o build_out",
        test="crystal spec",
        network_build=True,
        image="crystallang/crystal:latest-alpine",
    ),
    "swiftpm": Spec(  # Swift on Linux (distinct from Mac/Xcode targets)
        driver="docker",
        build="swift build",
        test="swift test",
        test_filter="swift test --filter {filter}",
        network_build=True,
        image="swift:5.10",
    ),

    # ---- interpreted / bytecode (build = compile-check) ----
    "python": Spec(
        driver="docker",
        build="if [ -f requirements.txt ]; then pip install --user -q -r requirements.txt; fi; "
              "if [ -f pyproject.toml ]; then pip install --user -q -e . || true; fi; "
              "python -m compileall -q .",
        test="python -m pytest -q",
        test_filter="python -m pytest -q -k {filter}",
        dep_add="pip install --user -q {deps}",
        image="python:3.12-slim-bookworm",
    ),
    "node": Spec(
        driver="docker",
        build="npm install --no-audit --no-fund && npm run build --if-present",
        test="npm test --silent",
        test_filter="npm test --silent -- {filter}",
        dep_add="npm install --no-audit --no-fund {deps}",
        network_build=True,
        image="node:22-bookworm-slim",
    ),
    "typescript": Spec(
        driver="docker",
        build="if [ -f package.json ]; then npm install --no-audit --no-fund && "
              "(npm run build --if-present); else tsc --noEmit $(find . -name '*.ts'); fi",
        test="if [ -f package.json ]; then npm test --silent; else echo 'no tests'; fi",
        dep_add="npm install --no-audit --no-fund {deps}",
        network_build=True,
        image="node:22-bookworm-slim",
    ),
    "deno": Spec(
        driver="docker",
        build="deno check $(find . -name '*.ts')",
        test="deno test --allow-none 2>/dev/null || deno test",
        image="denoland/deno:latest",
    ),
    "ruby": Spec(
        driver="docker",
        build="if [ -f Gemfile ]; then bundle install --quiet; fi; "
              "ruby -c $(find . -name '*.rb' | head -50)",
        test="if [ -f Rakefile ]; then rake test; else ruby -Itest test/*_test.rb; fi",
        dep_add="gem install {deps}",
        network_build=True,
        image="ruby:3.3-slim",
    ),
    "php": Spec(
        driver="docker",
        build="if [ -f composer.json ]; then composer install --quiet; fi; "
              "for f in $(find . -name '*.php'); do php -l \"$f\" || exit 1; done",
        test="./vendor/bin/phpunit || phpunit",
        dep_add="composer require {deps}",
        network_build=True,
        image="php:8.3-cli",
    ),
    "perl": Spec(
        driver="docker",
        build="for f in $(find . -name '*.pl' -o -name '*.pm'); do perl -c \"$f\" || exit 1; done",
        test="if [ -d t ]; then prove -l t/; else perl -c $(find . -name '*.pl' | head -1); fi",
        image="perl:5.40-slim",
    ),
    "lua": Spec(
        driver="docker",
        build="for f in $(find . -name '*.lua'); do luac -p \"$f\" || exit 1; done",
        test="if [ -f .busted ] || command -v busted >/dev/null; then busted; "
             "else lua $(find . -name '*_test.lua' -o -name 'test*.lua' | head -1); fi",
        image="nickblah/lua:5.4",
    ),
    "elixir": Spec(
        driver="docker",
        build="if [ -f mix.exs ]; then mix deps.get && mix compile; "
              "else elixirc $(find . -name '*.ex'); fi",
        test="mix test",
        network_build=True,
        image="elixir:1.17-slim",
    ),

    # ---- JVM / .NET / Dart (build-tool driven) ----
    "jvm": Spec(
        driver="docker",
        build="gradle --no-daemon assemble",
        test="gradle --no-daemon test",
        test_filter="gradle --no-daemon test --tests {filter}",
        network_build=True,
        image="gradle:8-jdk21",
    ),
    "kotlin": Spec(
        driver="docker",
        build="if [ -f build.gradle ] || [ -f build.gradle.kts ]; then gradle --no-daemon assemble; "
              "else kotlinc $(find . -name '*.kt') -include-runtime -d build_out.jar; fi",
        test="if [ -f build.gradle ] || [ -f build.gradle.kts ]; then gradle --no-daemon test; "
             "else echo 'no gradle project'; fi",
        network_build=True,
        image="gradle:8-jdk21",  # kotlinc added in the Dockerfile
    ),
    "scala": Spec(
        driver="docker",
        build="sbt compile",
        test="sbt test",
        network_build=True,
        image="sbtscala/scala-sbt:eclipse-temurin-21.0.2_13_1.9.9_3.4.0",
    ),
    "dotnet": Spec(
        driver="docker",
        build="dotnet build",
        test="dotnet test",
        test_filter="dotnet test --filter {filter}",
        dep_add="dotnet add package {deps}",
        network_build=True,
        image="mcr.microsoft.com/dotnet/sdk:8.0",
    ),
    "dart": Spec(
        driver="docker",
        build="if [ -f pubspec.yaml ]; then dart pub get && dart analyze; else dart analyze; fi",
        test="dart test",
        network_build=True,
        image="dart:stable",
    ),
}

DOCKER_LANGS = frozenset(n for n, s in LANGUAGES.items() if s.driver == "docker")
MAC_LANGS = frozenset({"swift", "objc", "xcodeproj"})

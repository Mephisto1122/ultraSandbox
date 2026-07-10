# Supported languages

22 Docker languages (local, isolated containers) + 3 Mac languages (remote EC2 Mac).

Network column: ● = standard build needs the network, so create with `allow_network=true`; ○ = builds fully offline.

| Language | Driver | Base image | Network | Build | Test |
|---|---|---|---|---|---|
| `go` | docker | `golang:1.24-bookworm` | ○ | `go build ./...` | `go test ./...` |
| `c` | docker | `gcc:13-bookworm` | ○ | `if [ -f CMakeLists.txt ]; then cmake -S . -B build && cmake …` | `if [ -d build ]; then ctest --test-dir b…` |
| `cpp` | docker | `gcc:13-bookworm` | ○ | `cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug && cmake --buil…` | `ctest --test-dir build --output-on-failu…` |
| `rust` | docker | `rust:1.84-slim-bookworm` | ● | `cargo build` | `cargo test` |
| `zig` | docker | `alpine:3.20` | ○ | `if [ -f build.zig ]; then zig build; else zig build-exe $(fi…` | `if [ -f build.zig ]; then zig build test…` |
| `haskell` | docker | `haskell:9.8-slim` | ● | `if [ -f *.cabal ] \|\| ls ./*.cabal >/dev/null 2>&1; then caba…` | `if ls ./*.cabal >/dev/null 2>&1; then ca…` |
| `crystal` | docker | `crystallang/crystal:latest-alpine` | ● | `crystal build $(find . -name '*.cr' ! -path '*/spec/*' \| hea…` | `crystal spec` |
| `swiftpm` | docker | `swift:5.10` | ● | `swift build` | `swift test` |
| `python` | docker | `python:3.12-slim-bookworm` | ○ | `if [ -f requirements.txt ]; then pip install --user -q -r re…` | `python -m pytest -q` |
| `node` | docker | `node:22-bookworm-slim` | ● | `npm install --no-audit --no-fund && npm run build --if-prese…` | `npm test --silent` |
| `typescript` | docker | `node:22-bookworm-slim` | ● | `if [ -f package.json ]; then npm install --no-audit --no-fun…` | `if [ -f package.json ]; then npm test --…` |
| `deno` | docker | `denoland/deno:latest` | ○ | `deno check $(find . -name '*.ts')` | `deno test --allow-none 2>/dev/null \|\| de…` |
| `ruby` | docker | `ruby:3.3-slim` | ● | `if [ -f Gemfile ]; then bundle install --quiet; fi; ruby -c …` | `if [ -f Rakefile ]; then rake test; else…` |
| `php` | docker | `php:8.3-cli` | ● | `if [ -f composer.json ]; then composer install --quiet; fi; …` | `./vendor/bin/phpunit \|\| phpunit` |
| `perl` | docker | `perl:5.40-slim` | ○ | `for f in $(find . -name '*.pl' -o -name '*.pm'); do perl -c …` | `if [ -d t ]; then prove -l t/; else perl…` |
| `lua` | docker | `nickblah/lua:5.4` | ○ | `for f in $(find . -name '*.lua'); do luac -p "$f" \|\| exit 1;…` | `if [ -f .busted ] \|\| command -v busted >…` |
| `elixir` | docker | `elixir:1.17-slim` | ● | `if [ -f mix.exs ]; then mix deps.get && mix compile; else el…` | `mix test` |
| `jvm` | docker | `gradle:8-jdk21` | ● | `gradle --no-daemon assemble` | `gradle --no-daemon test` |
| `kotlin` | docker | `gradle:8-jdk21` | ● | `if [ -f build.gradle ] \|\| [ -f build.gradle.kts ]; then grad…` | `if [ -f build.gradle ] \|\| [ -f build.gra…` |
| `scala` | docker | `sbtscala/scala-sbt:eclipse-temurin-21.0.2_13_1.9.9_3.4.0` | ● | `sbt compile` | `sbt test` |
| `dotnet` | docker | `mcr.microsoft.com/dotnet/sdk:8.0` | ● | `dotnet build` | `dotnet test` |
| `dart` | docker | `dart:stable` | ● | `if [ -f pubspec.yaml ]; then dart pub get && dart analyze; e…` | `dart test` |

## Mac languages
| Language | Tool | Notes |
|---|---|---|
| `swiftpm` | `swift build` (Linux) | runs in Docker, not Mac |
| `swift` | `xcodebuild` / SwiftPM | remote EC2 Mac |
| `xcodeproj` | `xcodebuild` | remote EC2 Mac; `target`/`filter` = scheme |
| `objc` | `xcodebuild` | remote EC2 Mac |

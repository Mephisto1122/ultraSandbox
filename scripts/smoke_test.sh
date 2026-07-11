#!/usr/bin/env bash
# Real end-to-end smoke test — run this where Docker IS available.
# For each language: builds the image, starts a hardened sandbox, boots a
# container with the same flags the driver uses, and reports.
#   ./scripts/smoke_test.sh            # all languages
#   ./scripts/smoke_test.sh go rust    # a subset
set -uo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null || { echo "Docker not found — start Docker Desktop first."; exit 1; }

ALL=(go c cpp rust zig haskell crystal swiftpm python node typescript deno \
     ruby php perl lua elixir jvm kotlin scala dotnet dart)
LANGS=("${ALL[@]}"); [ $# -gt 0 ] && LANGS=("$@")

pass=0; fail=0; failed=()
for lang in "${LANGS[@]}"; do
  dir="ultra_sandbox/images/$lang"
  [ -d "$dir" ] || { echo "SKIP  $lang"; continue; }
  printf "%-12s building image... " "$lang"
  if ! docker build -q -t "ultra-sandbox/$lang" "$dir" >/dev/null 2>/tmp/us_$lang.log; then
    echo "IMAGE BUILD FAILED (/tmp/us_$lang.log)"; fail=$((fail+1)); failed+=("$lang"); continue
  fi
  net=none
  case "$lang" in rust|node|typescript|jvm|kotlin|scala|dotnet|dart|ruby|php|elixir|haskell|crystal|swiftpm) net=bridge;; esac
  cid=$(docker run -d --network "$net" --cap-drop ALL --security-opt no-new-privileges \
        --pids-limit 512 --memory 2g --cpus 2 --read-only \
        --tmpfs /tmp:rw,exec,size=256m -v "us_smoke_$lang:/work" -w /work \
        -e HOME=/work/.home "ultra-sandbox/$lang" sleep infinity 2>/tmp/us_run_$lang.log)
  if [ -z "$cid" ]; then
    echo "boot FAILED (/tmp/us_run_$lang.log)"; fail=$((fail+1)); failed+=("$lang")
    docker volume rm -f "us_smoke_$lang" >/dev/null 2>&1; continue
  fi
  docker exec "$cid" sh -lc 'mkdir -p /work/.home' >/dev/null 2>&1
  echo "image + hardened container ✓"
  pass=$((pass+1))
  docker rm -f "$cid" >/dev/null 2>&1; docker volume rm -f "us_smoke_$lang" >/dev/null 2>&1
done
echo "----------------------------------------"
echo "$pass built + booted, $fail failed"
[ $fail -gt 0 ] && { echo "Failed: ${failed[*]}"; exit 1; }
echo "All good."

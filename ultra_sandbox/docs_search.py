"""search_docs backend.

Design (from the build plan):
- Called mid-repair-loop when an error mentions an API Claude is unsure about.
- Backed by web search hard-restricted to first-party doc domains (the
  "allowlist" answer to the plan's open question — predictable beats flexible
  for a tool that runs inside an automated loop).
- Cached per session so repeated lookups in one repair loop don't re-hit the
  network.
- Returns short snippets + source URLs, not page dumps, so the model reads and
  paraphrases rather than copying documentation wholesale.

Provider: Brave Search API (BRAVE_API_KEY env var). Adding another provider
means implementing one function; see _search_brave.
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

import httpx

from .config import Config

# Nudge the query toward the right corner of the allowlist per language.
LANG_HINTS: dict[str, str] = {
    "go": "site:pkg.go.dev",
    "swift": "site:developer.apple.com",
    "objc": "site:developer.apple.com",
    "xcodeproj": "site:developer.apple.com",
    "node": "site:nodejs.org OR site:developer.mozilla.org",
    "python": "site:docs.python.org",
    "rust": "site:doc.rust-lang.org OR site:docs.rs",
    "cpp": "site:en.cppreference.com OR site:cmake.org",
    "dotnet": "site:learn.microsoft.com",
    "jvm": "site:docs.oracle.com",
}


class DocsSearch:
    def __init__(self, config: Config):
        self.config = config
        self._cache: dict[tuple[str, str], dict] = {}

    def search(self, query: str, lang: str | None = None) -> dict:
        key = (query.strip().lower(), (lang or "").lower())
        if key in self._cache:
            return {**self._cache[key], "cached": True}

        provider = self.config["docs"]["provider"]
        if provider == "none":
            result = {
                "results": [],
                "sources": [],
                "note": "Docs search is disabled ([docs].provider = 'none'). "
                        "Enable the 'brave' provider and set BRAVE_API_KEY.",
            }
        elif provider == "brave":
            result = self._search_brave(query, lang)
        else:
            result = {"results": [], "sources": [],
                      "note": f"Unknown docs provider {provider!r}."}

        self._cache[key] = result
        return {**result, "cached": False}

    # ---------- providers ----------

    def _search_brave(self, query: str, lang: str | None) -> dict:
        api_key = os.environ.get("BRAVE_API_KEY", "")
        if not api_key:
            return {
                "results": [], "sources": [],
                "note": "BRAVE_API_KEY is not set. Export it in the environment that "
                        "launches the MCP server, or set [docs].provider = 'none'.",
            }
        q = query
        if lang and (hint := LANG_HINTS.get(lang.lower())):
            q = f"{query} {hint}"
        try:
            resp = httpx.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": q, "count": 10},
                headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as e:
            return {"results": [], "sources": [], "note": f"Docs search failed: {e}"}

        allow = set(self.config["docs"]["allowlist"])
        results, sources = [], []
        for item in (payload.get("web", {}).get("results") or []):
            url = item.get("url", "")
            host = urlparse(url).netloc.removeprefix("www.")
            if host not in allow:
                continue
            results.append({
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("description", "")[:400],
            })
            sources.append(url)
            if len(results) >= 5:
                break
        note = None
        if not results:
            note = ("No allowlisted documentation matched. Either broaden the query "
                    "or add the relevant doc domain to [docs].allowlist.")
        return {"results": results, "sources": sources, **({"note": note} if note else {})}

#!/usr/bin/env python3
"""S0 preflight: the installed pi must expose every extension API TextFold for
Pi relies on. Exits 0 with a one-line OK, else exits 1 naming the missing API.

Looked up in this order: TEXTFOLD_PI_CLI's package dirdist tree, the npm global
install, then the newest npx cache entry.
"""
import glob, os, re, sys

WANT = {
    "registerMarkdownTransformer": "F-C1 in-place fold",
    "registerShortcut": "key UX",
    "registerFlag": "digit-guard flag (C2)",
    "appendEntry": "level persistence (C1)",
    "registerEntryRenderer": "custom entry rendering",
    "getEditorText": "digit-guard reinsertion (C2)",
    "setEditorText": "digit-guard reinsertion (C2)",
}

def dist_candidates():
    cands = []
    cli = os.environ.get("TEXTFOLD_PI_CLI", "")
    if cli:
        cands.append(os.path.join(os.path.dirname(cli), "..", ".."))
    cands += [
        os.path.expanduser("~/.npm-global/lib/node_modules/@earendil-works/pi-coding-agent/dist"),
    ] + sorted(glob.glob(os.path.expanduser(
        "~/.npm/_npx/*/node_modules/@earendil-works/pi-coding-agent/dist")), reverse=True)
    return [c for c in cands if os.path.exists(c)]

def main():
    types = None
    for dist in dist_candidates():
        f = os.path.join(dist, "core", "extensions", "types.d.ts")
        if os.path.exists(f):
            types = f
            break
    if not types:
        print("FAIL: no pi-coding-agent dist found; set TEXTFOLD_PI_CLI", file=sys.stderr)
        return 1
    text = open(types, encoding="utf-8").read()
    missing = [api for api in WANT if not re.search(rf"\b{re.escape(api)}\s*[<(]", text)]
    if missing:
        print("FAIL", types)
        for api in missing:
            print(f"  missing {api}  (needed for {WANT[api]})")
        return 1
    print(f"OK: all {len(WANT)} extension APIs present in {types}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

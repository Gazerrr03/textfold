# A page from the reader's own browser

Status: a first version (branch `capture`), tried locally. Not in a release.

TextFold fetches a web page without running its scripts and without the reader's sign-in. That misses a page the
reader can read and TextFold cannot: signed in, past a paywall they pay for, behind a bot wall (Medium, Stack
Overflow, The Economist), drawn by scripts, or kept in shadow roots. The page as the reader's browser drew it is the
one to read. Reading how to parse and show such a page comes after; this is how it comes.

## The way in

```
the reader clicks TextFold's button  ->  extension/background.js
  runs extension/snapshot.js in the tab's frames (activeTab, scripting)
  sends {format: textfold/snapshot, url, title, html, taken} by native messaging
the browser starts TextFold's host  ->  python3 -m textfold capture-host (textfold/capture.py)
  checks it (a web page's address, a page, at most 64 MB)
  stores it as a web page of the library: web-<host>-<hash>, snapshot.html beside it, never over a page already there
  answers {ok, paper, new, open}: open is the reader's address when TextFold is running (server.json)
the extension shows ✓ (or ! and why) and opens the reader beside the page
```

The snapshot (`extension/snapshot.js`): shadow roots spelled out, closed ones too (`chrome.dom.openOrClosedShadowRoot`,
an extension's), their slots filled; each frame the tab lets it into put where its iframe is; an element the browser
does not show marked `data-tf-css-hidden`. Reading it, a hidden element hanging on a mark (1, [12], *) is a note, and
the rest stays out (`webpage._hover_marks`, `_hidden_out`).

## Why this way

- **Only an extension reaches the session the reader is using.** Since Chrome 136 the remote-debugging port no
  longer opens the default profile, because cookie stealers used it; copying a profile gives a stale copy and acts
  like one. Chrome 144's auto-connect asks every session and is Chrome's alone.
- **No `debugger`.** Tools that let an agent drive the browser (Playwright MCP's extension, chrome-devtools-mcp)
  need it, and with it every tab. Reading the page the reader clicked on needs `activeTab`; folding in place later
  needs a content script, and a site's optional permission to do it unasked. An agent works on the snapshot, never
  on the browser.
- **No port.** Native messaging: the browser starts the host and lets only the extensions named in its manifest
  reach it. Local servers without authentication have been reached by pages and other extensions.
- **The cookies stay.** What is sent is the page as drawn; it stays in the reader's library.

## Tried

`tools/capture_e2e.py`: the extension in Playwright's Chromium, its host registered in that browser's own profile,
pages served locally: a subscriber's article (a cookie; without it, a teaser too short to read), a page drawn by its
script, text in an open and in a closed shadow root with a hidden note on a mark, a page in a frame, the same page
again (not written over), and the reader opened beside the page while TextFold runs. `tests/test_capture.py` and
`tests/extension.test.cjs` hold the rest without a browser.

## Not yet

- Windows (the host is registered in the registry there) and the desktop app registering the host itself, with its
  own Python, when it starts.
- The extension in the Chrome Web Store (its id fixed), Firefox (`browser.runtime.connectNative`, the same host),
  Safari (an extension inside a signed app).
- A page read again: a newer snapshot of a page already in the library (kept beside the old, or replacing it).
- Deciding whether a page is an article at all (a feed, a front page) before reading it.
- Parsing and showing: the reader on the snapshot, then folding the live page in place.

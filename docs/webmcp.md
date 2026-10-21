# Browser reading tools

TextFold registers 19 tools with `document.modelContext.registerTool` on its landing and reader pages. A browser host
with WebMCP support discovers and invokes them directly. Browsers without WebMCP keep the normal interface; TextFold
does not install a synthetic registry or claim browser support through a REST manifest.

The registration follows the [WebMCP draft](https://webmachinelearning.github.io/webmcp/), a Draft Community Group Report dated 20 October 2026, not a W3C Standard. Tool results use
text content containing JSON, including actionable failures. The browser may attach a document-specific suffix to
tool names; discover the current catalog again after navigation.

| Tools | Purpose |
| --- | --- |
| `library-query`, `library-open` | Find and open existing reading documents; list folders |
| `file-import` | Upload a supplied file through the same operation as file selection or drag/drop |
| `zotero-query`, `zotero-import` | Find items, enumerate exact attachments, import the selected cached PDF |
| `documentation-preview`, `documentation-import` | Inspect a directory without writing, or import it directly as one work |
| `documentation-update`, `documentation-retry` | Explicit source refresh, or fetch only failed pages |
| `folder-create`, `folder-rename`, `document-move` | Organize the existing library |
| `reading-context`, `reading-navigate` | Current selection, original passage/formula and surrounding context; chapter/unit navigation |
| `annotation-list`, `annotation-create`, `annotation-update`, `annotation-delete` | Saved notes/highlights in the existing notes format |
| `processing-status` | Import/generation jobs, readable content, failed chapters, unresolved annotations |

An annotation is written only when the user requests saving or marking. Asking about a passage does not create a
note. New marks require a source unit and a unique exact quote from that unit; generated summaries are not treated
as author text. `reading-context` returns source text and a paged outline (40 sections by default, up to 100).

## Documentation sets

The importer selects the documentation root from the starting path and reads the largest navigation directory
within that root, preserving its order and expandable group hierarchy. Same-page fragments collapse to one source
page; unrelated site paths stay out. A site without a readable directory returns an actionable error instead of
guessing a whole-site crawl. Content must be present in the server's HTML; sign-in and JavaScript-only sites may
require another source.

One library item stores the directory in `documentation.json`, individual page snapshots in `pages/`, and the composed
semantic document in `source.html`. Chapters retain source URLs; headings, code, images, tables and matching internal
chapter links use the existing semantic reader. Images use the existing local image importer.

The live reader opens one source chapter at a time, with the ordered directory and previous/next controls in the
existing top bar. This bounds the zoom scene for large documentation sets. All chapters remain in the same work;
generation and whole-document HTML export use the complete document. Unit ids stay global, so chapter changes and
the notes menu can navigate to a saved mark in another chapter.

Import starts the normal generation queue automatically, while Full remains readable. `reading_mode: original`
asks the model for concise levels in each passage's original language, without invoking translation. The historical
base-layer storage slot remains `layers/en.json`; the interface labels it Original for these documents.

Repeated imports open the existing work without generation. Explicit update refreshes the directory and pages;
retry fetches only failed pages, retaining successful snapshots. A failed update fetch may retain the previous
chapter snapshot, and is still reported as failed. The Sources menu names missing chapters and offers retry.

On updates, source-page identity plus original text/quotes remap paragraph notes. Section anchors retain their
stable chapter/heading identity. Unmatched annotations keep their text and original quote with `unresolved: true`
and no active passage anchor; the result and Sources menu report them. When source text changes, old generated layers move to `previous/layers/` and the normal queue generates current levels. An unchanged source and repeated imports retain their existing layers. The browser restores the reading
level and exact source passage across reloads, falling back to its source page if that passage changed.

## Zotero

Use `zotero-query` with an exact `item` (`users/0/KEY` or `groups/ID/KEY`) to enumerate attachments, then pass the
selected attachment key to `zotero-import`. Multiple PDFs return `needs: attachment` rather than choosing another
version. A missing exact cache returns `needs: zotero-cache` with a retry instruction. TextFold reads the existing
llm-for-zotero cache; it neither produces that cache nor modifies the original PDF. New cached PDF imports queue
original-language generation; repeated imports open the existing copy without regeneration.

## Validation

`file-import` takes `name`, exactly one of `text` (Markdown/plain text) or `base64` (original bytes),
and optional `lang` (otherwise the upload menu's reading language). The existing 100 MiB limit applies.
Text uploads require a selected model; binary files can return readable source, a conversion job, or
`needs: engine`. A source being readable does not mean generation completed: follow `processing-status`.
Conversion/generation failures retain the existing upload/source receipts for retry. Relative Markdown images
follow the existing upload behavior. `node --test tests/webmcp-file-import.test.cjs` checks the shared operation.

Run `python -m unittest discover tests`. `tests/test_documentation.py` covers directory order/hierarchy, fragment
deduplication, readable partial imports, failed-page-only retry, repeated import reuse, source provenance, internal
links, update remapping, unresolved notes, all-page failure recovery, and Chinese base-layer generation without a
translation call. Browser acceptance must additionally exercise the host's actual tool catalog and calls; REST
tests alone do not establish WebMCP delivery.

## Compatible agents and desktop use

Tools are page-local. Discovery and execution require a supporting browser-agent host; TextFold provides no
standalone MCP server and does not make every Codex client WebMCP-capable. Unsupported browsers retain the usual UI.

A researcher can discuss a selected passage or equation with an external browser agent, and explicitly ask it to
save a source-anchored note. An agent can import a synthetic reviewer-comments file through the same operation as
drag/drop, follow its job, open an ordered documentation directory, or select a cached Zotero PDF by attachment key.

Desktop users can open the desktop app's actual local server URL in a supporting browser. The desktop app chooses
an available port starting at 31917; the developer server's 3017 is not a fixed desktop address. This operates that
service/library. Direct external-agent access to the Electron window has not been established. Selection, zoom and
chapter state belong to the browser view executing the tool; desktop selections are not automatically synchronized.

The optional [WebMCP skill from Builder.io's Agent-Native skills collection](https://github.com/BuilderIO/skills/blob/main/skills/webmcp/SKILL.md)
can guide compatible agents through discovery, invocation and result verification. It is not required by TextFold,
is not an OpenAI-official skill, and does not supply browser WebMCP support.

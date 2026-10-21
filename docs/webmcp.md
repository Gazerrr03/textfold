# Browser reading tools

TextFold registers 15 page-local tools through `document.modelContext.registerTool` on its landing and reader pages.
They adapt existing TextFold operations. Agents need a browser integration that can discover and invoke page-local
WebMCP tools; validation here used Codex's in-app browser. Ordinary MCP support alone does not provide that browser
capability, and installing the optional skill below does not add it. Unsupported browsers retain the normal
interface. There is no standalone MCP server or synthetic REST tool registry.

| Tools | Purpose |
| --- | --- |
| `library-query`, `library-open` | Find existing documents/folders and open a document |
| `file-import` | Import supplied text or file bytes through the shared upload operation |
| `zotero-query`, `zotero-import` | List/search Zotero and read an item through the existing importer |
| `folder-create`, `folder-rename`, `document-move` | Organize the library |
| `reading-context`, `reading-navigate` | Read selection/source/formula context and navigate a unit or section |
| `annotation-list`, `annotation-create`, `annotation-update`, `annotation-delete` | Read and explicitly save/edit/delete notes and highlights |
| `processing-status` | Follow existing jobs and readable documents |

Tool names may acquire host-specific suffixes. Rediscover the current catalog after navigation. Results are text
content containing JSON; errors are marked `isError`. Schemas accompany each registered tool.

## Reading and annotations

A reader can discuss the exact selected source passage or equation with a browser agent, then explicitly ask it to
save a note. Discussion alone writes nothing. `reading-context` accepts an optional `unit` and paged section outline
(`offset`, `limit`, default 40, maximum 100). It returns current language/level, selected text, source text, surrounding
units, and selected display-equation source HTML. `reading-navigate` accepts `unit` or `section` and optional `level`
(0 Topic through 4 Full). It operates within the current document.

`annotation-list` accepts an optional current `paper`. Create takes `unit`, unique exact source `quote` and optional
`text`; update takes `id`, `text` and optionally a replacement `unit`/`quote`; delete takes `id`. Notes use the existing
notes format. Generated summaries are not treated as source quotes. Annotation operations require the document open.

## Files and Zotero

`file-import` takes `name`, exactly one of `text` (Markdown/plain text) or `base64` (original bytes), and optional `lang`.
The selected reading language is the default. It uses the same dispatch, PDF-reference discovery and existing
100 MiB limit as file selection/drop. Text imports require a selected model. Binary files can return a readable
source, a conversion job or `needs: engine`. Follow `processing-status` using the returned job/paper; readability
does not establish completed generation. Existing upload/source receipts are retained on conversion failure.

`zotero-query` without arguments lists libraries; `library` (such as `users/0` or `groups/42`) and optional `query`
search its items. Pass the returned library/key identity as `item` to `zotero-import`, with optional `lang`. This
uses the author's existing importer: its supported online reference or selected local attachment, with the normal
conversion/generation flow. Attachment selection and language generation follow the existing importer's behavior.

`library-query` accepts optional `query`/`folder`; `library-open` takes `paper`. Folder create takes `name`, rename
`id`/`name`, and document move `papers`/`folder` (empty folder moves out). `processing-status` accepts `job`, `paper`
and optional `open` to open readable content; it starts no new generation.

## Compatibility and validation

Desktop users must open TextFold's actual localhost URL in a compatible agent-controlled browser. Desktop ports start at
31917; development defaults to 3017. Direct external-agent access to Electron is unverified. Selection and zoom
belong to the executing browser view; desktop selections are not synchronized automatically.

The optional [Builder.io Agent-Native WebMCP skill](https://github.com/BuilderIO/skills/blob/main/skills/webmcp/SKILL.md)
can guide discovery, calls and result verification. It is not required, is not OpenAI-official, and does not provide
host support. The [WebMCP specification](https://webmachinelearning.github.io/webmcp/) remains a draft.

Run `python -m unittest discover tests` and `node --test tests/webmcp-file-import.test.cjs`. Browser acceptance must
also discover the actual registered catalog and invoke representative tools against isolated data/ports; REST-only
tests do not establish WebMCP delivery.

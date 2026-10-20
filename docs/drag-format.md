# Dragged out of the reader (`textfold/drag`, version 1)

What the reader gives an app when a part of a text is dragged into it (a notes app, an editor): the text as it reads
at the level shown, where it is, and a `textfold://` link back to exactly there, which the desktop app opens
(`desktop/README.md`, Links). Fields may be added without a new version; a field renamed or removed comes with
version 2.

## What is dragged

| Dragged | `kind` | The link | `text` |
|---|---|---|---|
| a paragraph, by the handle beside it on hover (its text stays selectable) | `paragraph` | `u=<id>&level=<level>` | the paragraph at its level |
| a chip on the Topic map, by its handle | `chip` | `u=<id>&level=topic` | its topic |
| a section's heading, by its handle | `section` | `s=<id>&level=<level>` | its number and title |
| a section's one-line summary (Key, Takeaway, Topic), by its handle | `summary` | `s=<id>&level=<level>` | the summary |
| a selection | `selection` | `u=<the paragraph it starts in>&level=<level>` (`s=` when it starts on a heading or summary) | the selected words |
| a highlight's or a note's card, in the margin or the notes list | `note` | `n=<note id>` | the note's text, else its quote |
| a conversation's card (Ask) | `ask` | `n=<note id>` | the answer in one sentence |

Every link is `textfold://open?paper=<id>&…&lang=<code>`, the language the text was read in, values URL-encoded.

## The four types

- `text/plain`: Markdown that reads well anywhere: the text (a note's or a conversation's quote) as a quote, then
  the note's text, or the question in bold and the answer, then `— [<title> › <section>](textfold://…)`.
- `text/uri-list`: the link.
- `text/html`: the same, as a `<blockquote>` and a link, in a `<div data-textfold="…">` that holds the JSON below:
  a custom type may not survive from one app to another, HTML does.
- `application/x-textfold+json`: the JSON.

## The JSON

```json
{
  "format": "textfold/drag",
  "version": 1,
  "paper": "2512.23916",
  "title": "…",
  "authors": ["…"],
  "citekey": "wei2022",
  "section": { "id": "S3", "num": "3", "title": "Method" },
  "kind": "paragraph",
  "level": "key",
  "lang": "en",
  "text": "…",
  "written": true,
  "quote": "…",
  "comment": "…",
  "link": "textfold://open?paper=2512.23916&u=S3.p2&level=key&lang=en"
}
```

- **paper**, **title**, **authors**: the document's id, its title as the reader shows it (the name the reader gave it
  in the library, else its title in `lang`), its authors as stored.
- **citekey**: the Zotero item's, for a document read from an item's own file (its meta's `zotero`); left out
  otherwise.
- **section**: the section it is in, `null` outside any (a document's opening text, the whole paper).
- **level**: the level shown when it was dragged: `topic`, `takeaway`, `key`, `brief` or `full`.
- **lang**: the language it was read in.
- **text**: what was dragged, as it reads at that level, in plain text: a formula as `$LaTeX$`, a gap as `…`.
- **written**: `true` when `text` is the model's words: a paragraph or selection at Key, Takeaway or Topic, a
  summary, a conversation's answer. (A translation is the model's too: `lang` says which language it is.)
- **quote**: the passage, for a note, a conversation and a selection, when there is one.
- **comment**: the reader's own words, when there are any: a note's text, a conversation's first question.
- **link**: the `textfold://` link back.

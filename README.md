<div align="center">

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/logo.svg" width="72" alt="TextFold">

# TextFold

**Fold any text, from a one-screen map to every word**

<sub>Formerly PaperFold</sub>

<img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-6B5CE7?style=flat-square">
<img alt="Runs on your computer" src="https://img.shields.io/badge/runs-on_your_computer-E08A3C?style=flat-square">
<a href="https://github.com/chenxiachan/textfold/blob/main/LICENSE"><img alt="Apache License 2.0" src="https://img.shields.io/badge/license-Apache_2.0-6B5CE7?style=flat-square"></a>

**English** · [简体中文](https://github.com/chenxiachan/textfold/blob/main/README.zh-CN.md)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/sources-dark.webp">
  <img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/sources.webp" width="880" alt="What TextFold reads: arXiv, PubMed Central, bioRxiv, medRxiv, Wikipedia, GitHub READMEs, any web page, PDF, Word, PowerPoint, Excel, EPUB, HTML, pictures, Markdown, text, CSV and an agent's replies, folded from the full text down to a few words">
</picture>

**Paste a link:** any web page · arXiv · PubMed Central · bioRxiv · medRxiv · Wikipedia · GitHub<br>
**Drop files, one or several:** PDF · Word · PowerPoint · Excel · EPUB · HTML · CSV · pictures · Markdown · text

**[Try the demo →](https://chenxiachan.github.io/textfold/gallery/)** or **[download the app ↓](#get-started)** · [What's new ↓](#whats-new)

<br>

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/zoom.gif" width="880" alt="A paper folding from its full text into a map of its sections, and back">

</div>

## Read with less in your head

Choose the level of detail you need, and lower your cognitive load.

| | Level | Each paragraph becomes | In whose words |
|:-:|---|---|---|
| **1** | **Full** | the paragraph as written | the author's |
| **2** | **Brief** | its one to three key sentences, verbatim | the author's |
| **3** | **Key** | its point and the reason for it | AI, resting on the Brief sentences |
| **4** | **Takeaway** | one line on the spine of its section | AI |
| **5** | **Topic** | a few words; the text becomes a map of section cards | AI |

## Also for agent output

Your agent writes more than you have time to read. A [Claude Code mod](https://code.claude.com/docs/en/plugins/mods/overview) folds every reply the same way, one key per level, and an extension does the same in Pi. [More ↓](#in-claude-code-and-pi)

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/textfold.gif" width="880" alt="A reply in Claude Code folding from the full text to two sentences a paragraph, then one, and back, one key at a time">

## One fold, three places

- **Read.** Paste a link or drop a file; it opens as a map of its sections that you zoom into. [Get started ↓](#get-started)
- **Fold your agent's replies.** One key per level in Claude Code and in Pi, with no second model. [In Claude Code and Pi ↓](#in-claude-code-and-pi)
- **Plug it into your workflow.** `python3 -m textfold get` hands your agent or script a document one level at a time, and an open format lets any program read and write folded text. [For agents ↓](#for-agents-and-scripts)

## What you get

- **Words that travel.** As you zoom, every word that stays slides to its new place and the rest fade around it.
- **Zoom under your fingers.** Stop halfway, turn back, or open one paragraph alone.

- **Beside the original.** Open a paper's or a PDF's own pages next to the text, each paragraph shown where it stands on its page.
- **Ask AI about exactly what you read.** Select a passage, or ask about the whole text. The answer comes structured: the short answer first, then the evidence, each point citing the paragraph it rests on, one click away.
- **Notes that zoom with the text.** Highlight and write in the margin; what you marked stays as you zoom out, and is saved with the page.

- **Your language.** Read in many languages, translated sentence by sentence, with every formula as typeset.

- **Your library, in order.** Search it with ⌘K, keep documents in folders (drag one in, or right-click it), and list it by kind, by when each came in, or by when you last opened it.

<table>
<tr>
<td width="50%"><img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/notes.png" alt="Highlights in the full text and a note in the margin"></td>
<td width="50%"><img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/keep.png" alt="The highlighted passages kept at the Takeaway level"></td>
</tr>
<tr>
<td align="center"><sub>Highlight and write in the margin…</sub></td>
<td align="center"><sub>…and keep what you marked as you zoom out.</sub></td>
</tr>
</table>

## Works on your Zotero

Click **Zotero library**, under the drop zone, and your library is there as Zotero shows it: your collections, your group libraries, a search. **Read** opens any item.

- **An item on arXiv** opens from arXiv. Any other opens from its PDF, with the PDF beside the text, or from the EPUB, saved web page or Word file it holds. An item with only a DOI opens from Europe PMC.
- **It keeps what you entered in Zotero:** the title, the authors and the citekey.
- **It stays on your computer.** TextFold asks the Zotero app you already run, the way citation plugins do: no account, no key, nothing sent to Zotero's servers, and nothing in your library changed.

To turn it on, in Zotero 7: **Settings › Advanced › Allow other applications on this computer to communicate with Zotero**.

## Get started

**[Download the app](https://chenxiachan.github.io/textfold/#download)** for macOS (Apple silicon or Intel) or Windows. Everything it needs is inside, Python included.

Or install the Python package, on any system and for your own pipeline:

```bash
python3 -m pip install textfold
python3 -m textfold serve
```

Open `http://localhost:3017`. The first time, [connect a model](#connect-a-model); then paste a link or drop a file, and pick a language. You need Python 3.9 or newer (the one macOS ships with works).

| Paste or drop | What TextFold reads |
|---|---|
| A paper's link or DOI: arXiv, PubMed Central, bioRxiv, medRxiv | its text as the site structures it (an arXiv paper without an HTML version is read from its PDF; another DOI needs an open full text in Europe PMC) |
| Any other web page | its article, without the menus, the adverts, or the text it hides from its readers |
| A Wikipedia article, a GitHub repository | the article; the README, with its pictures |
| A PDF | the paper online when the PDF names one, with your file beside it; any other PDF, on your computer: read by TextFold itself, figures included, or more completely by the PDF engine (MinerU, about 3.4 GB, installed once from the landing), which a scanned PDF needs |
| A Word, PowerPoint or Excel file, a CSV, an EPUB, a saved web page | the document with its headings, tables, pictures and formulas: read by TextFold itself, or more completely by the PDF engine once it is installed |
| A picture | its text, read by the PDF engine |
| An item of your Zotero library | its arXiv paper, else its PDF or other file, else its DOI. [Works on your Zotero ↑](#works-on-your-zotero) |
| A Markdown or text file | the file as written |

What you read is kept in your system's folder for app data, shared with the desktop app.

<details>
<summary>Run it from the code instead</summary>

```bash
git clone https://github.com/chenxiachan/textfold.git
cd textfold
python3 -m pip install -r requirements.txt
python3 -m textfold serve
```

What you read is then kept in the clone.

</details>

## Connect a model

TextFold uses a model you already have, and there is no account to create. It looks for one when it starts; if it finds none, the first page offers the ways in.

| You have | What to do |
|---|---|
| Claude Code, Codex, Pi or WorkBuddy | Nothing. TextFold finds it and uses it. WorkBuddy (experimental) brings its models, on your WorkBuddy sign-in; CodeBuddy's own CLI works too. |
| A ChatGPT plan | Click **Use my ChatGPT plan**. A small bridge starts on your computer and signs in with your account (needs Node.js). |
| Nothing yet | Click **OpenRouter in one click**. Authorize once, and free models are ready. |
| An API key | **Settings › Add provider**: Anthropic, OpenAI, DeepSeek, Qwen, Zhipu GLM, Kimi, MiniMax, Google, Ollama, or any OpenAI-compatible endpoint. |

Your questions can go to a stronger model than the one that writes the levels: **Settings › Models › Answering questions**, with how hard it reasons.

## In the reader

| Do | To |
|---|---|
| Pinch, or ⌘ / Ctrl + scroll | zoom around the pointer |
| `1` to `5` | jump to a level |
| **Cards** or **Map**, beside the levels at Topic | the sections and their topics as cards, or as a mind map |
| Click a paragraph | open just that paragraph |
| Click a figure | see it enlarged |
| **Original**, at the top | read beside the paper's PDF |
| **Save**, at the top | keep the page as one file, as Markdown at the level you read, or only your notes |
| **Aa**, at the top | light or dark, the default or paper style, the text's size, serif or sans-serif, the line spacing, the column's width, and which margins show |
| `F` | focus: the text alone, the bars back at the screen's edge |
| Select text | highlight, write a note, or ask |
| **Ask the paper**, bottom right | ask about the whole text |
| `L` | next language |
| `⌘K` (Ctrl+K) or `/` | search your library |
| ⌘ / Ctrl or Shift + click in the sidebar | pick several documents, to move into a folder or delete together |
| The pin, at the top of the sidebar | keep the sidebar open beside the text |

## For agents and scripts

`python3 -m textfold get` gives a document one level at a time, coarsest first, so an agent reads the map before it spends its context on the whole text:

```bash
python3 -m textfold get https://arxiv.org/abs/2512.23916        # the map: every section's topic
python3 -m textfold get 2512.23916 --level key --section 3      # one section: its points, each with its reason
python3 -m textfold get report.pdf --json                       # the whole document, in the TextFold format
```

A document not folded yet is folded first, with the model you connected. Every line a model wrote is marked as such and anchored to the author's sentences it rests on: [docs/format.md](https://github.com/chenxiachan/textfold/blob/main/docs/format.md) describes the format, for any program that reads or writes folded text.

A running TextFold (the app, or `python3 -m textfold serve`) says where it is in `server.json`, in its data folder (`~/Library/Application Support/TextFold` on a Mac, `%LOCALAPPDATA%\TextFold` on Windows, `~/.local/share/textfold` on Linux, the clone when run from one): `{"format": "textfold/server", "version": 1, "url": "http://127.0.0.1:<port>", "port": <port>, "pid": <pid>, "textfold": "<version>", "started": "<UTC time>"}`. The file goes when the server stops; one left behind (a server ended outright) names an address that answers nothing.

An agent in a browser that offers WebMCP, a draft web standard (tried in Codex's own browser), finds TextFold's own operations on its pages as tools: it reads the passage you are reading or selected, and, when you ask, saves a note on an exact passage, imports a file or a Zotero item, or sorts your folders. Nothing changes in a browser without it. [docs/webmcp.md](https://github.com/chenxiachan/textfold/blob/main/docs/webmcp.md) lists the tools. Contributed by [@peitianyi23-sudo](https://github.com/peitianyi23-sudo).

## Save a page

**Save**, at the top of the reader, keeps a page as one HTML file that opens anywhere without a server: its levels, the notes you choose and, if you like, its original PDF to read beside it. It can also keep the whole text as Markdown at the level you are reading, your notes under their paragraphs (at Topic, an outline that a mind-map plugin draws), or only your notes, as a page, a PDF, Markdown for Obsidian or JSON. From the command line, the page without your notes:

```bash
python3 -m textfold export 2512.23916
```

TextFold is a tool, and its license covers its code. When you share a file, follow the terms of the original text, shown under its title.

## In Claude Code and Pi

TextFold puts the five levels on every reply in Claude Code and in Pi. Press 5 for the answer in one sentence, 3 for the point of every paragraph, 1 for every word (in Pi, hold Alt). Nothing is paraphrased, so at every level you read exactly what the model said.

<details>
<summary><b>In Claude Code: install it, and see what each level gives you</b></summary>

<br>

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/textfold.gif" width="880" alt="A reply in Claude Code folding from the full text to two sentences a paragraph, then one, and back, one key at a time">

It needs Claude Code 2.1.287 or later, in the terminal or in the Code tab of the Desktop app.

```bash
claude plugin marketplace add chenxiachan/textfold
claude plugin install textfold@textfold
```

| Key | Level | What you get |
|:-:|---|---|
| **1** | **Full** | every word Claude wrote |
| **2** | **Brief** | each point, with the reason behind it |
| **3** | **Points** | just the points, at a glance |
| **4** | **Outline** | the map of a long reply: its sections, and what each one says (a reply without headings shows its points) |
| **5** | **Gist** | the answer, in one sentence |

Type the digit while the prompt is empty, or pick a level in the row above the prompt. Short replies stay whole: one under about 80 words, or one a fold would barely shorten, always shows as written.

**Start folded.** A session starts at Full. To start at another level, run `/config` and set **Starting level**; in the session, the row above the prompt and the keys 1 to 5 still change it.

**Why you can trust a fold.** TextFold asks Claude to lead with the point: the answer first in every reply, the key sentence first in every paragraph. A fold keeps what Claude put first. There is no second model and no summary, so a fold costs nothing and takes no time.

More in [plugins/textfold](https://github.com/chenxiachan/textfold/blob/main/plugins/textfold/README.md).

</details>

<details>
<summary><b>In Pi: install it, and see it fold</b></summary>

<br>

<img src="https://raw.githubusercontent.com/chenxiachan/textfold/main/docs/assets/pi-think.gif" width="880" alt="A coding turn in Pi, its thinking and its reply, folding a level at a time until each is one sentence, by key and by a click on the row">

An extension puts the same five levels on every reply in [Pi](https://pi.dev). It needs Pi 1.2.0 or later, on Node 22.15 or later.

```bash
git clone https://github.com/chenxiachan/textfold.git
pi install ./textfold/plugins/pi-textfold
```

Hold Alt and type the digit, click a level in the row above the prompt, or type `/fold` and a level: `/fold 3`, `/fold points`, `/fold off`. Every reply folds in place, the earlier ones too, and so does the model's thinking, so a long coding turn reads in a few lines. The level stays with the session, and `/fold calibrate` teaches the keys on any keyboard. On a Mac, let the terminal send Option as Meta, or Option+1 types ¡. It folds with the mod's own engine, so a reply reads the same at each level in Claude Code and in Pi.

More in [plugins/pi-textfold](https://github.com/chenxiachan/textfold/blob/main/plugins/pi-textfold/README.md). Contributed by [@jlamweil](https://github.com/jlamweil).

</details>

## What's new

- **October 21, 2026: a reader to stay in.** **Aa** has light or dark (or your system's) and a paper style, quieter than white, for either; and the line spacing. A text opens where you left it, with a line under the top bar for how far in you are. `F` leaves the text alone on the screen. The sidebar can be pinned beside the text.
- **October 21, 2026: tools for an agent in your browser.** In a browser that offers WebMCP, an agent finds TextFold's own operations as tools: it reads the passage you selected and, when you ask, saves a note on it, imports a file or a Zotero item, or sorts your folders. [The tools](https://github.com/chenxiachan/textfold/blob/main/docs/webmcp.md). Thanks to [@peitianyi23-sudo](https://github.com/peitianyi23-sudo).
- **October 21, 2026: Topic as a mind map.** At Topic, **Map** beside the levels draws the sections and their topics as a mind map: click a topic to read its paragraph, click a section to fold it. Headings stand apart more clearly, **Aa** can hide the margins (the links, the AI answers, your notes), and **Save** keeps the whole text as Markdown at the level you read. On Windows, the installer asks where to install.
- **October 20, 2026: your type, and several documents at once.** **Aa** at the top sets the text's size, the column's width and serif or sans-serif, for every text. In the sidebar, ⌘-click (Ctrl-click) or Shift-click picks several documents to move into a folder or delete together, and a delete can be undone for a few seconds.
- **October 20, 2026: several files at once.** Drop or choose several files together: they are read, and their levels written, one after another while you go on reading, and the sidebar shows each.
- **October 20, 2026: TextFold and Obsidian.** [TextFold Bridge](https://github.com/adalach/obsidian-textfold-bridge), an Obsidian plugin, links your notes to places in TextFold: a paragraph, a section, a note. Drag a paragraph, a section or a selection from the reader into a note and it keeps a link back to where it came from. A note of your own folds at the five levels inside Obsidian, and after an edit it folds again in place, its comments found again in the new text. Thanks to [@adalach](https://github.com/adalach).
- **October 20, 2026: Pi folds the thinking too.** In Pi, the model's reasoning folds with its reply, so a long coding turn reads in a few lines. Click a level in the row to fold, keep your level when you resume a session, and teach the keys once with `/fold calibrate` on any keyboard. Thanks to [@jlamweil](https://github.com/jlamweil).
- **October 19, 2026: more languages to read in.** Swedish, Danish, Norwegian, Finnish, Dutch, Polish, Czech, Ukrainian, Turkish, Indonesian and Vietnamese join the languages a text can be read in. Where the interface has no words for a language, it is in English. Thanks to [@Kullenej](https://github.com/Kullenej).
- **October 15, 2026: Pi's replies fold too.** [An extension for Pi](https://github.com/chenxiachan/textfold/blob/main/plugins/pi-textfold/README.md) puts the five levels on every reply, with the same fold as in Claude Code. Thanks to [@jlamweil](https://github.com/jlamweil).
- **October 15, 2026: PDFs open without the engine.** A PDF with its own text, as most papers have, opens at once, its figures cut from the page; only a scan still needs the PDF engine. An arXiv paper with no HTML version is read from its PDF. Thanks to [@sylvainHellin](https://github.com/sylvainHellin).
- **October 15, 2026: your library, and your questions.** Search the library, keep documents in folders, and list them by when they came in or were last opened. A question has its own send and stop, any turn of a conversation can be deleted, and questions can go to a stronger model than the one that writes the levels. Thanks to [@suhyungJang](https://github.com/suhyungJang).
- **October 14, 2026: an app for Mac and Windows.** Download TextFold for macOS (Apple silicon or Intel, signed and notarized by Apple) or Windows, with everything it needs inside. It finds Claude Code, Codex or Pi on your computer, and updates itself when you say so. [Download ↓](#get-started)

<details>
<summary>Earlier</summary>

- **October 14, 2026: your Zotero library.** **Zotero library**, under the drop zone, shows your library and its collections as Zotero does, and opens any item in a click: from arXiv when it is there, else from its own PDF. Thanks to [@adalach](https://github.com/adalach). [Works on your Zotero ↑](#works-on-your-zotero)
- **October 14, 2026: arXiv pages, read more safely.** What could run script in a page is taken out before the reader draws it, and its figures stay as they were. Thanks to [@neil-patel77](https://github.com/neil-patel77).
- **October 13, 2026: save a page as one file.** **Save**, at the top of the reader, keeps the page as one HTML file, with your notes and its original PDF if you like, or only your notes. [Save a page ↓](#save-a-page)
- **October 13, 2026: Word, PowerPoint, Excel, e-books and more.** Drop a Word, PowerPoint or Excel file, a CSV, an EPUB or a saved web page, and it opens at once, formulas included, with nothing more to install.
- **October 13, 2026: whole figures, and a guide.** A figure the PDF engine cut into pieces now comes out whole, cut from its page. A short guide opens on your first visit, and again from **How it works**.
- **October 9, 2026: PaperFold is now TextFold.** The same reader, named for everything it folds: papers, web pages, PDFs, READMEs and your agent's replies. Links to the old repository lead here, and your settings move over by themselves.
- **October 9, 2026: any web page, and PDFs.** Paste any web page's link and read its article at five levels, without the text the page hides from its readers. Drop a PDF: when it names a paper that can be read online, that version opens with your PDF beside it; any other PDF is converted on your computer.
- **October 9, 2026: for agents.** `python3 -m textfold get <link> --level topic` prints a document's map, and `--section` unfolds the part that matters. [More ↓](#for-agents-and-scripts)
- **October 8, 2026: any GitHub README.** Paste a repository's link and read its README at five levels, with its logo, badges and GIFs as on GitHub.
- **October 8, 2026: read beside the original.** **Original**, at the top of a paper, opens its PDF at the left and shows each paragraph on its page as you read. A new paper opens as soon as it can be read, while its levels are written.
- **October 7, 2026: your agent's replies fold too.** [The Claude Code mod](#in-claude-code-and-pi) puts the five levels on every reply. Press 5 for the answer in one sentence, 1 for every word.
- **October 6, 2026: more than arXiv.** PubMed Central, bioRxiv, medRxiv, Wikipedia in any language, and your own Markdown files.

</details>

<br>

## Contributors

<a href="https://github.com/neil-patel77" title="@neil-patel77"><img src="https://github.com/neil-patel77.png?size=80" width="40" height="40" alt="@neil-patel77" /></a>
<a href="https://github.com/adalach" title="@adalach"><img src="https://github.com/adalach.png?size=80" width="40" height="40" alt="@adalach" /></a>
<a href="https://github.com/suhyungJang" title="@suhyungJang"><img src="https://github.com/suhyungJang.png?size=80" width="40" height="40" alt="@suhyungJang" /></a>
<a href="https://github.com/sylvainHellin" title="@sylvainHellin"><img src="https://github.com/sylvainHellin.png?size=80" width="40" height="40" alt="@sylvainHellin" /></a>
<a href="https://github.com/jlamweil" title="@jlamweil"><img src="https://github.com/jlamweil.png?size=80" width="40" height="40" alt="@jlamweil" /></a>
<a href="https://github.com/lamegoat" title="@lamegoat"><img src="https://github.com/lamegoat.png?size=80" width="40" height="40" alt="@lamegoat" /></a>
<a href="https://github.com/Kullenej" title="@Kullenej"><img src="https://github.com/Kullenej.png?size=80" width="40" height="40" alt="@Kullenej" /></a>
<a href="https://github.com/666xz666" title="@666xz666"><img src="https://github.com/666xz666.png?size=80" width="40" height="40" alt="@666xz666" /></a>
<a href="https://github.com/peitianyi23-sudo" title="@peitianyi23-sudo"><img src="https://github.com/peitianyi23-sudo.png?size=80" width="40" height="40" alt="@peitianyi23-sudo" /></a>
<a href="https://github.com/mcardZH" title="@mcardZH"><img src="https://github.com/mcardZH.png?size=80" width="40" height="40" alt="@mcardZH" /></a>
<a href="https://github.com/momoko-sketch" title="@momoko-sketch"><img src="https://github.com/momoko-sketch.png?size=80" width="40" height="40" alt="@momoko-sketch" /></a>
<a href="https://github.com/Knoety" title="@Knoety"><img src="https://github.com/Knoety.png?size=80" width="40" height="40" alt="@Knoety" /></a>

Contributions are welcome: start with [CONTRIBUTING.md](https://github.com/chenxiachan/textfold/blob/main/CONTRIBUTING.md).

<br>

<div align="center">

**If TextFold helps you read, ⭐ star it so others can find it.**

</div>

---

<div align="center">

<sub>Built on [trafilatura](https://github.com/adbar/trafilatura), which finds the article on a web page, [pdf-inspector](https://github.com/firecrawl/pdf-inspector), which reads a PDF's own text, [PDFium](https://pdfium.googlesource.com/pdfium/) by way of [pypdfium2](https://github.com/pypdfium2-team/pypdfium2), which cuts its figures, [MinerU](https://github.com/opendatalab/MinerU), the PDF engine, and [mammoth](https://github.com/mwilliamson/python-mammoth), which reads Word files; PDFs are shown with [PDF.js](https://github.com/mozilla/pdf.js) and formulas with [KaTeX](https://katex.org). Thanks to their authors.</sub>

[Apache 2.0](https://github.com/chenxiachan/textfold/blob/main/LICENSE) © 2026 Xia Chen · [Development](https://github.com/chenxiachan/textfold/blob/main/docs/DEVELOPMENT.md) · [Format](https://github.com/chenxiachan/textfold/blob/main/docs/format.md) · [Contributing](https://github.com/chenxiachan/textfold/blob/main/CONTRIBUTING.md) · [Security](https://github.com/chenxiachan/textfold/blob/main/SECURITY.md) · [Feedback](https://github.com/chenxiachan/textfold/issues)

</div>

# Contributing to TextFold

Thank you for helping. TextFold is small on purpose: a Python server with no framework, and a reader in plain JavaScript. How it works, and where everything lives, is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## One rule above the others

No change may make the zoom less smooth. If you touch the reader, measure before and after, as [Smoothness is a rule](docs/DEVELOPMENT.md#smoothness-is-a-rule) describes, and put both numbers in your pull request.

## Set up

```bash
git clone https://github.com/chenxiachan/textfold.git
cd textfold
python3 -m pip install -r requirements.txt
python3 -m textfold serve
```

Then open `http://localhost:3017` and connect a model (the README says how).

## Good places to start

- **A paper that reads wrong.** Open an issue with its arXiv ID, the level and language, and the paragraph (a screenshot is fine). Most fixes go in `textfold/parse.py`, which turns arXiv's HTML into paragraphs, formulas and citations.
- **A language.** A text can be read in every language listed in `textfold/langs.py`: one line adds one. The interface's words are in `textfold/web/i18n.js` and `textfold/web/tutorial.js`, in fewer languages; a text read in one they do not have shows the interface in English. A new interface language needs every table of both files and the desktop app's menu (`tests/test_languages.py` checks).
- **A model provider.** Presets and model lists are in `textfold/providers.py` and `textfold/models.py`.
- **A web page or a PDF that reads wrong.** Web pages go through `textfold/webpage.py`, PDFs through `textfold/pdfdoc.py` (the PDF engine's output into paragraphs, headings, figures and formulas).
- **The format.** Programs that read or write folded text follow [docs/format.md](docs/format.md); a reader of it in another language is welcome.

## Pull requests

- One change per pull request: what it changes, why, and how you checked it.
- Run the tests before you send it: `python3 -m unittest discover tests` (they need nothing more than the requirements, and touch none of your papers).
- Match the code around it: plain names, and comments that say why rather than what.
- Keep keys and papers out of commits. Settings and keys live in `~/.textfold/`; papers and their levels in `papers/`, which git ignores.

Sign off every commit (`git commit -s`). The line it adds, `Signed-off-by: Your Name <you@example.com>`, certifies the [Developer Certificate of Origin](https://developercertificate.org): that you wrote the change, or have the right to submit it, under this project's license. Your work is then released under the [Apache License 2.0](LICENSE).

A security problem goes to [SECURITY.md](SECURITY.md), not to an issue.

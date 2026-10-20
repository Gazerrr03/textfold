// textfold:// links, which other programs (an editor's plugin) open the app with, and the reader's address each one
// opens. Nothing here touches Electron, so node tests it alone (links.test.js).
//
//   textfold://open?paper=<document id>[&u=<paragraph id>][&n=<note id>][&level=<level>][&lang=<code>]
//     → <server>/p/<id>?lang=<code>#u=<paragraph id>&level=<level>, or #n=<note id>&level=<level>
//
// A link may come from any program, a web page among them, so every part is checked, and a link with one part wrong is
// not followed at all. It only ever opens a page of the reader: a document not in the library opens the landing.

// a document's id, as textfold/store.py's valid_id has it (tests/test_desktop_links.py keeps the two the same)
const ARXIV_ID = String.raw`\d{4}\.\d{4,5}`;
const IMPORTED_ID = String.raw`md-[a-z0-9]+(?:-[a-z0-9]+)*|pmc\d{4,9}|ppr\d{4,9}|(?:biorxiv|medrxiv)-[0-9.]{3,40}|wiki-[a-z][a-z-]{1,15}-\d{1,10}`
  + String.raw`|gh-[a-z0-9-]{1,39}--[a-z0-9._-]{1,100}|(?:pdf|doc)-[0-9a-f]{16}|web-[a-z0-9-]{1,40}-[0-9a-f]{12}`;
// the levels (textfold/fold.py), and the languages a text can be read in (textfold/langs.py)
const LEVELS = ['topic', 'takeaway', 'key', 'brief', 'full'];
const LANGS = ['en', 'zh', 'zh-Hant', 'ja', 'ko', 'es', 'fr', 'de', 'pt', 'it', 'ru', 'hi', 'sv', 'da', 'nb', 'fi', 'nl', 'pl',
  'cs', 'uk', 'tr', 'id', 'vi'];

const ARXIV = new RegExp(`^(?:${ARXIV_ID})$`);
const IMPORTED = new RegExp(`^(?:${IMPORTED_ID})$`);
const PART = /^[\w.-]+$/;   // a paragraph's id (S3.p2), a note's (n-k2x9q0ab)

function validId(id) {
  return ARXIV.test(id) || (IMPORTED.test(id) && id.length <= 80);
}

const CHECK = {
  paper: validId,
  u: (v) => PART.test(v),
  n: (v) => PART.test(v),
  level: (v) => LEVELS.includes(v),
  lang: (v) => LANGS.includes(v),
};

// A link's parts ({paper, u, n, level, lang}, those it has), or null when it is not one the app follows. Other
// parameters are left alone, so that a link a newer program makes still opens what this app knows of it.
function parse(link) {
  let url;
  try {
    url = new URL(String(link));
  } catch {
    return null;
  }
  // (textfold://open/?…, as some programs write it, is the same link)
  if (url.protocol !== 'textfold:' || url.host !== 'open' || !['', '/'].includes(url.pathname) || url.username || url.password) return null;
  const parts = {};
  for (const [key, check] of Object.entries(CHECK)) {
    const values = url.searchParams.getAll(key);
    if (values.length > 1 || (values.length && !check(values[0]))) return null;
    if (values.length) parts[key] = values[0];
  }
  return parts.paper ? parts : null;
}

// The reader's address for a link's parts, on the server at base (http://127.0.0.1:<port>). A note brings its own
// paragraph, so with one the paragraph is left out, as the reader would.
function readerUrl(base, parts) {
  const hash = [parts.n ? `n=${parts.n}` : parts.u ? `u=${parts.u}` : '', parts.level ? `level=${parts.level}` : ''].filter(Boolean).join('&');
  return `${base}/p/${parts.paper}${parts.lang ? `?lang=${encodeURIComponent(parts.lang)}` : ''}${hash ? `#${hash}` : ''}`;
}

// The link among a command line's arguments (Windows and Linux hand it to the app there), or null.
function fromArgv(argv) {
  return (argv || []).find((a) => typeof a === 'string' && /^textfold:/i.test(a)) || null;
}

module.exports = { parse, readerUrl, fromArgv, validId, ARXIV_ID, IMPORTED_ID, LEVELS, LANGS };

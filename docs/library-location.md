# The library's folder

The library is the documents (`papers/`: each with its levels, translations, notes and the model's replies, and the
trash), `library.json` (the folders, the order) and `zotero.json` (which Zotero item became which document). In
Settings, **Library folder** puts it in another folder from the next start, one of two ways:

- **Copy it into an empty folder.** When TextFold next starts, before its server answers, it copies the library there,
  checks every file against the one it came from, and then uses the copy. The library it was copied from stays as it
  was: nothing there is moved or deleted. A copy cut short (TextFold quit, the computer off) goes on at the next start
  from what it had copied. A file in the new folder that the copy did not write stops it, and so does a change to the
  library while it is copied: the library then stays where it was. The desktop app's window says it is copying, and
  waits for it (`desktop/main.js`).
- **Open a library already in a folder**, one with `papers/` in it: a library used before, or one from another
  computer. Nothing is copied or merged. TextFold uses it as it is, and what changed in the library it used until
  then stays there.

Until the next start everything is written where the library is now. A folder inside the library, or holding it, is
refused, and so is a library with links to other folders, which TextFold does not follow. Whatever goes wrong at the
start, the library stays where it was, and Settings says why.

The choice is kept in `.storage/<id>.json` in the data folder (`TEXTFOLD_DATA`; the clone, run from one; else the
system's data folder), one for each way TextFold runs (the desktop app, a pip install, a clone), so that one never
moves another's library, even where they share a data folder. Settings and keys (`~/.textfold`), uploads, the server's
own files and the PDF engine stay where they are (`textfold/storage_settings.py`).

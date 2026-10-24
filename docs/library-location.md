# Library location

The settings dialog offers two explicit actions, applied after restart:

- Copy to an empty folder: verify every document, notes file, model reply and library record; keep the source unchanged. Interrupted copies resume only their own journaled files. Conflicting destination changes stop the copy and leave the old library selected.
- Open an existing library: select its root containing `papers/`, including a library used before. No documents are copied, merged, overwritten or deleted. Changes in the previous library remain there.

The selection lives in `.storage/<runtime-id>.json` in the runtime data directory (`TEXTFOLD_DATA`, the checkout when run from source, or the normal installed-app data directory). Desktop, pip environments and source checkouts have separate stable runtime identities even when the default data directory is shared. It is not shared through `~/.textfold`: one checkout cannot redirect another installation. Model settings, credentials, uploads, server state and the PDF engine stay in their original locations. Existing global selections from the experimental branch are not imported automatically; select that library explicitly if desired.

Nothing happens when settings are merely opened. While a change is pending, all current writes still reach the old library. Startup selects the verified copy or revalidates the existing directory; any failure leaves the old library available and displays the error inline. Existing-library selection never merges two divergent libraries. Folder links and overlapping source/destination paths are rejected.

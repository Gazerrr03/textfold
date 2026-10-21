"""Read llm-for-zotero's existing MinerU output. Never start a conversion or write its cache."""
from contextlib import closing
import json
import re
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from . import engine, local, markdown, pdfdoc, store


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def find(lib, parent, attachment, pdf, data_dir):
    # Stored PDFs identify the active data directory even when Zotero moved from ~/Zotero.
    data = pdf.parents[2] if pdf.parent.parent.name == "storage" else Path(data_dir).expanduser()
    root = data / "llm-for-zotero-mineru"
    # Keys are library-local; the cache folder's numeric attachment ID belongs to this database.
    # Zotero holds an exclusive database lock. Read a private copy, never bypass locks on the live DB.
    try:
        with tempfile.TemporaryDirectory(prefix="textfold-zotero-db-") as tmp:
            db = Path(tmp) / "zotero.sqlite"
            shutil.copyfile(data / "zotero.sqlite", db)
            with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as conn:
                row = conn.execute("SELECT i.itemID FROM items i JOIN libraries l USING(libraryID) "
                                   "LEFT JOIN groups g USING(libraryID) WHERE i.key=? AND "
                                   "((?='users/0' AND l.type='user') OR g.groupID=?)",
                                   (attachment, lib, int(lib.split("/")[1]) if lib.startswith("groups/") else -1)).fetchone()
                if not row:
                    return None
                folder = root / str(row[0])
                if (folder / "_llm_write_pending.json").exists():
                    return None
                source = folder / "_llm_source.json"
                if source.exists():
                    identity = read_json(source)
                    if (identity.get("attachmentId"), identity.get("attachmentKey"), identity.get("parentItemKey")) != (row[0], attachment, parent):
                        return None
                else:
                    # Older local caches predate provenance files. The current database
                    # identifies their numeric folder and its exact parent within this library.
                    owner = conn.execute("SELECT p.key FROM itemAttachments a JOIN items p ON p.itemID=a.parentItemID "
                                         "WHERE a.itemID=?", (row[0],)).fetchone()
                    if not owner or owner[0] != parent:
                        return None
        if not (folder / "full.md").read_text(encoding="utf-8").strip():
            return None
        content = folder / "content_list.json"
        if not content.exists():
            content = next(iter(sorted(folder.glob("*_content_list.json"))), None)
        if content is None:
            # Finalized older caches can retain only Markdown and their manifest.
            return (folder, None) if isinstance(read_json(folder / "manifest.json"), dict) else None
        blocks = read_json(content)
        if isinstance(blocks, list) and blocks:
            return folder, blocks
    except (OSError, ValueError, sqlite3.Error):
        return None   # Zotero may be writing the database; try a fresh copy on the next poll.
    return None


def structured(blocks, folder, output, pdf, title):
    """MinerU content_list's 0..1000 boxes into TextFold's blocks and normalized page map."""
    pages, crops = {}, []
    geometry = folder / "figure_crops" / "figure_geometry.json"
    try:
        entries = read_json(geometry).get("entries", [])
    except (OSError, ValueError):
        entries = []
    for n, b in enumerate(blocks):
        kind, page = b.get("type"), int(b.get("page_idx", 0))
        source_kind = kind
        if kind == "chart":
            kind = "image"   # MinerU charts use the reader's existing figure/panel path.
        if kind == "discarded":
            continue
        box = [max(0, min(1, v / 1000)) for v in b.get("bbox", [])]
        content = b.get("text", "")
        out = {"type": kind, "content": content, "bbox": box}
        if kind == "text" and b.get("text_level"):
            out.update(type="paragraph_title", level=b["text_level"])
            if n == 0 and " ".join(content.split()) == " ".join(title.split()):
                out["type"] = "doc_title"
        if kind == "list":
            out["content"] = "\n".join("- " + x for x in b.get("list_items", []))
        if kind in ("image", "table"):
            caps = b.get(f"{source_kind}_caption", [])
            out["captions"] = [{"content": math_html(x), "bbox": box} for x in caps]
            out["footnotes"] = [{"content": x} for x in b.get(f"{source_kind}_footnote", [])]
            if kind == "table":
                out["content"] = math_html(b.get("table_body", ""))
                if not out["content"] and b.get("img_path"):
                    out["type"] = "image"
        if b.get("img_path") and (kind == "image" or not out["content"] or pdfdoc._figure_table({**out, "image_source": b["img_path"]})):
            source = folder / b["img_path"]
            label = re.search(r"(?:FIG(?:URE)?\.?|图)\s*(\d+)", " ".join(b.get(f"{source_kind}_caption", [])), re.I)
            if not source.is_file() and label:
                for entry in entries:
                    if re.search(r"(?:figure|fig\.?|图)\s*" + label[1] + r"\b", entry.get("label", ""), re.I):
                        crop = Path(entry.get("cropPath", ""))
                        crop = crop if crop.is_absolute() else folder / crop
                        if crop.is_file():
                            source = crop
                            break
                if not source.is_file():
                    source = next(iter(sorted((folder / "figure_crops/crops").glob(f"figure-{label[1]}-p{page + 1}.*"))), source)
            target = output / "images" / f"block-{n}.jpg"
            target.parent.mkdir(exist_ok=True)
            if source.is_file():
                target = target.with_suffix(source.suffix)
                shutil.copyfile(source, target)
            elif len(box) == 4:
                crops.append((page + 1, box, target))
            out["image_source"] = "images/" + target.name
        pages.setdefault(page, []).append(out)
    if crops:
        engine.crop_here(pdf, crops)   # PDF rendering only, with the app's existing pypdfium2
    return {"metadata": {"document": {"title": title}, "producer": {"name": "llm-for-zotero"}},
            "pages": [{"page_idx": p, "blocks": b} for p, b in sorted(pages.items())]}


def math_html(text):
    # Captions and table cells become HTML in pdfdoc; render their formulas before that boundary.
    def render(match):
        html, _ = markdown.to_html(match[0])
        return re.sub(r"^<p>|</p>\s*$", "", html.strip())
    return re.sub(r"\$\$[\s\S]+?\$\$|\$[^$\n]+\$", render, text)


def save(pid, cached, pdf, title):
    d = store.pdir(pid)
    if (d / "source.html").exists() and (d / "meta.json").exists():
        return pid   # layers and annotations belong to the already imported text
    folder, blocks = cached
    with tempfile.TemporaryDirectory(prefix="textfold-zotero-") as tmp:
        output = Path(tmp)
        sc = None
        if blocks is None:
            text, authors = (folder / "full.md").read_text(encoding="utf-8"), []
            output = folder
        else:
            sc = structured(blocks, folder, output, pdf, title)
            want = []
            pdfdoc.to_markdown(sc, pdf.name, want=want)
            jobs = [(w["page"], w["box"], output / "images" / f"figure-{n}.jpg") for n, w in enumerate(want)]
            done = engine.crop_here(pdf, jobs) if jobs else set()
            whole = {(p, tuple(box)): "images/" + f.name for p, box, f in jobs if str(f) in done}
            _, authors, text = pdfdoc.to_markdown(sc, pdf.name, crops=whole)
        html, _ = markdown.to_html(text)
        meta = {"id": pid, "version": "", "title": title, "authors": authors, "date": "", "doi": "",
                "snapshot": time.strftime("%Y-%m-%d"), "abs_url": "", "html_url": "", "license": "",
                "source": {"kind": "pdf", "name": pdf.name, "engine": "llm-for-zotero", "tier": ""},
                "label": "Zotero · " + title}
        local.store_doc(pid, html, meta, "source.md", text, lambda f: local.Images(f, output).resolve, sizes=True)
        shutil.copyfile(pdf, d / "source.pdf")
        if sc is not None:
            (d / "layout.json").write_text(json.dumps(pdfdoc.layout_of(sc), ensure_ascii=False), encoding="utf-8")
            (d / "structured_content.json").write_text(json.dumps(sc, ensure_ascii=False), encoding="utf-8")
    return pid

"""A picture kept with a document, made smaller as it comes in: a PNG or a JPEG (a BMP, a TIFF, a still WebP) as WebP
at quality 90, its longest side at most 3200 px. A paper's figures were most of what a library weighs: an arXiv paper's
came to 10 MB on average, the authors' PNGs as they uploaded them, and as WebP they keep a fifth of that, with nothing
to see at full size (photographs, plots, diagrams with small type compared side by side), and enough for the enlarged
view. A small picture (under 48 KB), one that moves (a GIF), a drawing (an SVG), one Pillow cannot read and one WebP
would not make at least a tenth smaller are kept as they came. Pictures already kept are not converted."""
import io

LONGEST = 3200
QUALITY = 90
SMALL = 48 * 1024
STILL = {"PNG", "JPEG", "MPO", "WEBP", "BMP", "TIFF"}


def compact(data, name):
    """(data, name) to keep: the picture as WebP, named name + ".webp" (so that two named alike stay two), or as it
    came."""
    if not data or len(data) < SMALL or name.lower().endswith((".svg", ".gif")):
        return data, name
    try:
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        if im.format not in STILL or getattr(im, "n_frames", 1) > 1:
            return data, name
        icc = im.info.get("icc_profile") if im.mode != "CMYK" else None   # (a CMYK profile does not fit RGB)
        im = ImageOps.exif_transpose(im)   # a photograph upright, as a browser shows a JPEG by its EXIF
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.mode or "transparency" in im.info else "RGB")
        im.thumbnail((LONGEST, LONGEST))
        buf = io.BytesIO()
        im.save(buf, "WEBP", quality=QUALITY, method=4, **({"icc_profile": icc} if icc else {}))
    except Exception:
        return data, name
    out = buf.getvalue()
    if len(out) > 0.9 * len(data):
        return data, name
    return out, name + ".webp"

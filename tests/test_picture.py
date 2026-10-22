"""Pictures kept smaller as they come in (picture.py): a large PNG or JPEG as WebP, at most 3200 px on its longest side,
upright as its EXIF says, transparent where it was; a small one, a GIF, an SVG and bytes that are no picture as they
came. Both ways pictures come in use it: an arXiv paper's figures (fetch.fetch_images, which keeps a picture kept
before as it is and does not download it again) and every other document's (local.Images). Nothing is downloaded:
the pictures are made here.

Run from the repo root:
    python3 -m unittest discover tests
"""
import base64
import io
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from textfold import fetch, local, picture


def photo(w, h, mode="RGB", fmt="PNG", **kw):
    """A picture with detail in it (noise over a gradient), so that it is large as a PNG, as a figure is."""
    rnd = random.Random(w * h)
    im = Image.new(mode, (w, h))
    im.putdata([tuple([(x * 255 // w + rnd.randrange(60)) % 256, (y * 255 // h) % 256, rnd.randrange(256)] + ([rnd.randrange(256)] if mode == "RGBA" else []))
                for y in range(h) for x in range(w)])
    buf = io.BytesIO()
    im.save(buf, fmt, **kw)
    return buf.getvalue()


class Compact(unittest.TestCase):
    def test_a_large_png_becomes_a_smaller_webp(self):
        data = photo(600, 400)
        out, name = picture.compact(data, "figure_3.png")
        self.assertEqual(name, "figure_3.png.webp")
        self.assertLess(len(out), 0.9 * len(data))
        im = Image.open(io.BytesIO(out))
        self.assertEqual((im.format, im.size), ("WEBP", (600, 400)))

    def test_at_most_3200_px(self):
        out, _ = picture.compact(photo(4000, 300), "wide.png")
        self.assertEqual(Image.open(io.BytesIO(out)).size, (3200, 240))

    def test_transparency_kept(self):
        out, _ = picture.compact(photo(500, 300, "RGBA"), "plot.png")
        self.assertEqual(Image.open(io.BytesIO(out)).mode, "RGBA")

    def test_a_photograph_upright(self):
        im = Image.open(io.BytesIO(photo(400, 300, fmt="JPEG", quality=95)))
        exif = Image.Exif()
        exif[0x0112] = 6   # (taken turned: shown turned a quarter clockwise)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=95, exif=exif.tobytes())
        out, name = picture.compact(buf.getvalue(), "IMG_0001.jpg")
        self.assertEqual((name, Image.open(io.BytesIO(out)).size), ("IMG_0001.jpg.webp", (300, 400)))

    def test_kept_as_they_came(self):
        small = photo(40, 30)
        self.assertEqual(picture.compact(small, "icon.png"), (small, "icon.png"))
        big = photo(600, 400)
        frames = [Image.open(io.BytesIO(big)), Image.open(io.BytesIO(photo(600, 401))).crop((0, 0, 600, 400))]
        buf = io.BytesIO()
        frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:])
        gif = buf.getvalue()
        self.assertEqual(picture.compact(gif, "demo.gif"), (gif, "demo.gif"))
        svg = b"<svg xmlns='http://www.w3.org/2000/svg'>" + b" " * 60000 + b"</svg>"
        self.assertEqual(picture.compact(svg, "drawing.svg"), (svg, "drawing.svg"))
        junk = b"\x89PNG not really" * 5000
        self.assertEqual(picture.compact(junk, "broken.png"), (junk, "broken.png"))


class Ways(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.img = Path(self.tmp.name) / "img"
        self.big = photo(600, 400)

    def tearDown(self):
        self.tmp.cleanup()

    def test_arxiv_figures(self):
        calls = []

        def get(url):
            calls.append(url)
            return self.big, url
        self.img.mkdir()
        (self.img / "old.png").write_bytes(self.big)   # kept before: as it came
        with mock.patch.object(fetch, "get", get):
            srcs = ["2401.00001v1/x1.png", "2401.00001v1/old.png", "2401.00001v1/x2.png"]
            got = fetch.fetch_images(srcs, "https://arxiv.org/html/2401.00001v1/", self.img)
            self.assertEqual(got, {"2401.00001v1/x1.png": "img/x1.png.webp", "2401.00001v1/old.png": "img/old.png",
                                   "2401.00001v1/x2.png": "img/x2.png.webp"})
            self.assertEqual(sorted(u.rsplit("/", 1)[-1] for u in calls), ["x1.png", "x2.png"])
            self.assertEqual(fetch.fetch_images(srcs, "https://arxiv.org/html/2401.00001v1/", self.img), got)
            self.assertEqual(len(calls), 2)   # (not downloaded again)
        self.assertEqual(sorted(f.name for f in self.img.iterdir()), ["old.png", "x1.png.webp", "x2.png.webp"])
        self.assertEqual((self.img / "old.png").read_bytes(), self.big)

    def test_other_documents(self):
        images = local.Images(self.img, None)
        src = "data:image/png;base64," + base64.b64encode(self.big).decode()
        self.assertEqual(images.resolve(src), "img/01-image.png.webp")
        small = "data:image/png;base64," + base64.b64encode(photo(40, 30)).decode()
        self.assertEqual(images.resolve(small), "img/02-image.png")
        with Image.open(self.img / "01-image.png.webp") as im:
            self.assertEqual(im.format, "WEBP")


if __name__ == "__main__":
    unittest.main()

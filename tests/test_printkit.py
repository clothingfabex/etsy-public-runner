"""Offline tests: synthetic images in a temporary folder only. No network, no credentials."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from printkit import checksums, pngspec, zipkit  # noqa: E402


def make_png(path, size=(450, 540), dpi=300, alpha=True, corner_opaque=False, fill=0.3):
    w, h = size
    im = Image.new("RGBA" if alpha else "RGB", size, (0, 0, 0, 0) if alpha else (255, 255, 255))
    box = (int(w * (0.5 - fill / 2)), int(h * (0.5 - fill / 2)), int(w * (0.5 + fill / 2)), int(h * (0.5 + fill / 2)))
    im.paste((200, 30, 40, 255) if alpha else (200, 30, 40), box)
    if corner_opaque and alpha:
        im.putpixel((0, 0), (1, 2, 3, 255))
    im.save(path, "PNG", dpi=(dpi, dpi))


class ZipKit(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.files = []
        for i in range(6):
            p = os.path.join(self.d, f"img_{i}.png")
            with open(p, "wb") as fh:
                fh.write(os.urandom(300_000))       # incompressible, ~0.3 MB each
            self.files.append(p)

    def tearDown(self):
        shutil.rmtree(self.d)

    def test_single_part(self):
        zs = zipkit.pack(self.files, os.path.join(self.d, "out"), "batch", 50 * 1024 * 1024)
        self.assertEqual(len(zs["parts"]), 1)
        self.assertEqual(zs["parts"][0]["filename"], "batch.zip")
        self.assertEqual(zipkit.verify_zipset(os.path.join(self.d, "out", "batch_zipset.json")), [])

    def test_parts_respect_limit_and_rebuild_byte_for_byte(self):
        limit = 700_000
        zs = zipkit.pack(self.files, os.path.join(self.d, "out"), "batch", limit)
        self.assertGreater(len(zs["parts"]), 1)
        self.assertTrue(all(p["size_bytes"] <= limit for p in zs["parts"]))
        ex = os.path.join(self.d, "rebuilt")
        self.assertEqual(zipkit.verify_zipset(os.path.join(self.d, "out", "batch_zipset.json"), ex), [])
        for p in self.files:
            self.assertEqual(open(p, "rb").read(), open(os.path.join(ex, os.path.basename(p)), "rb").read())

    def test_rebuild_is_byte_identical(self):
        a = zipkit.pack(self.files, os.path.join(self.d, "a"), "batch", 50 * 1024 * 1024)
        b = zipkit.pack(self.files, os.path.join(self.d, "b"), "batch", 50 * 1024 * 1024)
        self.assertEqual(a["parts"][0]["sha256"], b["parts"][0]["sha256"])

    def test_tampered_part_is_detected(self):
        zipkit.pack(self.files, os.path.join(self.d, "out"), "batch", 50 * 1024 * 1024)
        with open(os.path.join(self.d, "out", "batch.zip"), "r+b") as fh:
            fh.seek(100)
            fh.write(b"X")
        self.assertTrue(zipkit.verify_zipset(os.path.join(self.d, "out", "batch_zipset.json")))

    def test_file_larger_than_limit_is_refused(self):
        with self.assertRaises(ValueError):
            zipkit.pack(self.files, os.path.join(self.d, "out"), "batch", 100_000)

    def test_duplicate_names_refused(self):
        os.makedirs(os.path.join(self.d, "sub"))
        dup = os.path.join(self.d, "sub", "img_0.png")
        shutil.copy(self.files[0], dup)
        with self.assertRaises(ValueError):
            zipkit.pack(self.files + [dup], os.path.join(self.d, "out"), "batch", 50 * 1024 * 1024)


class Checksums(unittest.TestCase):
    def test_create_verify_detect_change_and_missing(self):
        d = tempfile.mkdtemp()
        try:
            for i in range(3):
                with open(os.path.join(d, f"f{i}.png"), "wb") as fh:
                    fh.write(os.urandom(1000))
            m = checksums.create(d, ("*.png",))
            self.assertEqual(len(m["files"]), 3)
            self.assertEqual(checksums.verify(d, m), [])
            with open(os.path.join(d, "f1.png"), "ab") as fh:
                fh.write(b"x")
            os.remove(os.path.join(d, "f2.png"))
            self.assertEqual(sorted(checksums.verify(d, m)), ["changed: f1.png", "missing: f2.png"])
        finally:
            shutil.rmtree(d)


class PngSpec(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.spec = pngspec.Spec(450, 540, 300)

    def tearDown(self):
        shutil.rmtree(self.d)

    def p(self, name, **kw):
        path = os.path.join(self.d, name)
        make_png(path, **kw)
        return path

    def test_good_file_passes(self):
        self.assertEqual(pngspec.check(self.p("ok.png"), self.spec), [])

    def test_each_failure_is_reported(self):
        self.assertTrue(any("size" in x for x in pngspec.check(self.p("s.png", size=(400, 500)), self.spec)))
        self.assertTrue(any("DPI" in x for x in pngspec.check(self.p("d.png", dpi=72), self.spec)))
        self.assertTrue(any("RGBA" in x for x in pngspec.check(self.p("a.png", alpha=False), self.spec)))
        self.assertTrue(any("corners" in x for x in pngspec.check(self.p("c.png", corner_opaque=True), self.spec)))
        self.assertTrue(any("visible" in x for x in pngspec.check(self.p("e.png", fill=0.05), self.spec)))

    def test_not_a_png(self):
        path = os.path.join(self.d, "x.png")
        Image.new("RGB", (10, 10)).save(path, "JPEG")
        self.assertEqual(pngspec.check(path, self.spec), ["not a PNG file"])


class Cli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "printkit", *args], cwd=ROOT, capture_output=True, text=True)

    def test_end_to_end(self):
        d = tempfile.mkdtemp()
        try:
            for i in range(3):
                make_png(os.path.join(d, f"d{i}.png"))
            r = self.run_cli("pngcheck", *[os.path.join(d, f"d{i}.png") for i in range(3)], "--width", "450", "--height", "540")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = self.run_cli("zip", d, "--out", os.path.join(d, "zips"), "--name", "set")
            self.assertEqual(r.returncode, 0, r.stderr)
            r = self.run_cli("unzip", os.path.join(d, "zips", "set_zipset.json"))
            self.assertEqual(r.returncode, 0, r.stdout)
            r = self.run_cli("sums", d, "--out", os.path.join(d, "sums.json"), "--pattern", "*.png")
            self.assertEqual(r.returncode, 0)
            r = self.run_cli("verify", d, os.path.join(d, "sums.json"))
            self.assertEqual(r.returncode, 0, r.stdout)
            r = self.run_cli("pngcheck", os.path.join(d, "d0.png"), "--width", "100", "--height", "100")
            self.assertEqual(r.returncode, 1)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()

"""Command line: python -m printkit <command> ...

  zip      DIR --out OUT --name BASE [--part-max-mb 200] [--pattern "*.png"]
  unzip    ZIPSET.json [--extract-to DIR]          verify parts (and optionally extract)
  sums     DIR --out MANIFEST.json [--pattern "*.png"]
  verify   DIR MANIFEST.json
  pngcheck FILE... --width W --height H [--dpi 300] [--no-alpha] [--allow-opaque-corners]

Exit code 0 = success / everything verified, 1 = a check failed, 2 = usage error.
"""
import argparse
import fnmatch
import json
import os
import sys

from . import checksums, pngspec, zipkit


def _matching(folder, pattern):
    return sorted(os.path.join(folder, n) for n in os.listdir(folder)
                  if os.path.isfile(os.path.join(folder, n)) and fnmatch.fnmatch(n.lower(), pattern.lower()))


def main(argv=None):
    p = argparse.ArgumentParser(prog="printkit")
    sub = p.add_subparsers(dest="cmd", required=True)
    z = sub.add_parser("zip")
    z.add_argument("dir")
    z.add_argument("--out", required=True)
    z.add_argument("--name", required=True)
    z.add_argument("--part-max-mb", type=float, default=200)
    z.add_argument("--pattern", default="*.png")
    u = sub.add_parser("unzip")
    u.add_argument("zipset")
    u.add_argument("--extract-to")
    s = sub.add_parser("sums")
    s.add_argument("dir")
    s.add_argument("--out", required=True)
    s.add_argument("--pattern", default="*")
    v = sub.add_parser("verify")
    v.add_argument("dir")
    v.add_argument("manifest")
    c = sub.add_parser("pngcheck")
    c.add_argument("files", nargs="+")
    c.add_argument("--width", type=int, required=True)
    c.add_argument("--height", type=int, required=True)
    c.add_argument("--dpi", type=int, default=300)
    c.add_argument("--no-alpha", action="store_true")
    c.add_argument("--allow-opaque-corners", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "zip":
        files = _matching(a.dir, a.pattern)
        if not files:
            print("no matching files", file=sys.stderr)
            return 2
        zs = zipkit.pack(files, a.out, a.name, int(a.part_max_mb * 1024 * 1024))
        for part in zs["parts"]:
            print(f"{part['filename']}: {len(part['entries'])} files, {part['size_bytes']} bytes, verified")
        return 0
    if a.cmd == "unzip":
        problems = zipkit.verify_zipset(a.zipset, a.extract_to)
    elif a.cmd == "sums":
        m = checksums.create(a.dir, (a.pattern,))
        checksums.save(m, a.out)
        print(f"{len(m['files'])} files listed in {a.out}")
        return 0
    elif a.cmd == "verify":
        problems = checksums.verify(a.dir, checksums.load(a.manifest))
    else:
        spec = pngspec.Spec(a.width, a.height, a.dpi, not a.no_alpha, not a.allow_opaque_corners)
        problems = []
        for f in a.files:
            problems += [f"{os.path.basename(f)}: {x}" for x in pngspec.check(f, spec)]
    for x in problems:
        print(x)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())

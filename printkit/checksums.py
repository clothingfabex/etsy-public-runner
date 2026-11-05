"""SHA-256 manifest for a folder of files: create it, then verify the folder against it later.

Local files only; no network access, no credentials.
"""
import fnmatch
import hashlib
import json
import os


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def _files(folder, patterns):
    out = []
    for name in sorted(os.listdir(folder)):
        p = os.path.join(folder, name)
        if os.path.isfile(p) and any(fnmatch.fnmatch(name.lower(), pat.lower()) for pat in patterns):
            out.append(p)
    return out


def create(folder, patterns=("*",)):
    files = _files(folder, patterns)
    return {"schema": "printkit.checksums.v1",
            "files": [{"name": os.path.basename(p), "sha256": sha256_file(p), "size_bytes": os.path.getsize(p)}
                      for p in files]}


def verify(folder, manifest):
    """Return a list of problems (empty = every listed file present and unchanged)."""
    problems = []
    for e in manifest["files"]:
        p = os.path.join(folder, e["name"])
        if not os.path.exists(p):
            problems.append(f"missing: {e['name']}")
        elif os.path.getsize(p) != e["size_bytes"] or sha256_file(p) != e["sha256"]:
            problems.append(f"changed: {e['name']}")
    return problems


def save(manifest, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)

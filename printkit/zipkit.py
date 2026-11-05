"""Pack files into one or more verified ZIP parts under a size limit.

* Files are never split across parts; every part is an ordinary, independently openable ZIP.
* Entries are stored uncompressed with a fixed timestamp, so rebuilding the same files gives
  byte-identical archives.
* A JSON "zipset" describes every part and the SHA-256 of every entry, so the original files
  can be verified or rebuilt from the parts later (see verify_zipset).

No network access, no credentials: local files only.
"""
import hashlib
import json
import os
import zipfile

FIXED_TIME = (2020, 1, 1, 0, 0, 0)
_EOCD = 22                       # end-of-central-directory record
_ENTRY_OVERHEAD = 30 + 46 + 64   # local header + central directory entry + margin


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def plan_parts(paths, part_max_bytes):
    """Group paths (order kept) so that no part exceeds part_max_bytes."""
    groups, cur, size = [], [], _EOCD
    for p in paths:
        need = os.path.getsize(p) + _ENTRY_OVERHEAD + 2 * len(os.path.basename(p).encode())
        if need + _EOCD > part_max_bytes:
            raise ValueError(f"{os.path.basename(p)} is larger than the part limit ({part_max_bytes} bytes)")
        if cur and size + need > part_max_bytes:
            groups.append(cur)
            cur, size = [], _EOCD
        cur.append(p)
        size += need
    if cur:
        groups.append(cur)
    return groups


def part_name(base, i, n):
    if n == 1:
        return f"{base}.zip"
    w = max(2, len(str(n)))
    return f"{base}_part{i:0{w}d}of{n:0{w}d}.zip"


def pack(paths, out_dir, base_name, part_max_bytes):
    """Write the part(s) and <base_name>_zipset.json into out_dir. Returns the zipset dict.
    Every part is re-opened and every entry compared with its source before returning."""
    names = [os.path.basename(p) for p in paths]
    if len(set(names)) != len(names):
        raise ValueError("two input files have the same file name")
    groups = plan_parts(paths, part_max_bytes)
    os.makedirs(out_dir, exist_ok=True)
    zipset = {"schema": "printkit.zipset.v1", "base": base_name, "part_max_bytes": part_max_bytes, "parts": []}
    for i, group in enumerate(groups, 1):
        zpath = os.path.join(out_dir, part_name(base_name, i, len(groups)))
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
            for p in group:
                with open(p, "rb") as fh:
                    z.writestr(zipfile.ZipInfo(os.path.basename(p), FIXED_TIME), fh.read())
        entries = []
        with zipfile.ZipFile(zpath) as z:
            if z.testzip() is not None:
                raise IOError(f"{zpath}: CRC check failed")
            for p in group:
                data = z.read(os.path.basename(p))
                with open(p, "rb") as fh:
                    if data != fh.read():
                        raise IOError(f"{zpath}: {os.path.basename(p)} differs from its source")
                entries.append({"name": os.path.basename(p), "sha256": hashlib.sha256(data).hexdigest(),
                                "size_bytes": len(data)})
        size = os.path.getsize(zpath)
        if size > part_max_bytes:
            raise IOError(f"{zpath} is {size} bytes, above the {part_max_bytes}-byte limit")
        zipset["parts"].append({"filename": os.path.basename(zpath), "sha256": _sha256_file(zpath),
                                "size_bytes": size, "entries": entries})
    with open(os.path.join(out_dir, f"{base_name}_zipset.json"), "w", encoding="utf-8") as fh:
        json.dump(zipset, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return zipset


def verify_zipset(zipset_path, extract_to=None):
    """Check every part and entry against the zipset. Optionally extract the verified files.
    Returns a list of problems (empty = everything verified)."""
    with open(zipset_path, encoding="utf-8") as fh:
        zs = json.load(fh)
    here = os.path.dirname(os.path.abspath(zipset_path))
    problems = []
    for part in zs["parts"]:
        zpath = os.path.join(here, part["filename"])
        if not os.path.exists(zpath):
            problems.append(f"missing part {part['filename']}")
            continue
        if _sha256_file(zpath) != part["sha256"]:
            problems.append(f"{part['filename']}: checksum mismatch")
            continue
        with zipfile.ZipFile(zpath) as z:
            for e in part["entries"]:
                data = z.read(e["name"])
                if hashlib.sha256(data).hexdigest() != e["sha256"]:
                    problems.append(f"{part['filename']}/{e['name']}: checksum mismatch")
                elif extract_to:
                    os.makedirs(extract_to, exist_ok=True)
                    with open(os.path.join(extract_to, os.path.basename(e["name"])), "wb") as out:
                        out.write(data)
    return problems

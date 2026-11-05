# etsy-public-runner

Small, **offline** command-line utilities for print-on-demand image files.
Everything runs on local files. Nothing here contacts a shop, a marketplace, a cloud drive or
an AI service, and nothing here needs credentials.

## Tools (`python -m printkit ...`)

| Command | What it does |
|---|---|
| `zip DIR --out OUT --name BASE [--part-max-mb 200] [--pattern "*.png"]` | Pack files into one or more ZIP parts under a size limit. Files are never split; each part is re-opened and checked against its sources; a `BASE_zipset.json` records the SHA-256 of every part and entry. Rebuilding the same files gives byte-identical archives. |
| `unzip ZIPSET.json [--extract-to DIR]` | Verify every part and entry against the zipset (and optionally extract the verified files). |
| `sums DIR --out MANIFEST.json [--pattern "*.png"]` | Write a SHA-256 manifest of a folder. |
| `verify DIR MANIFEST.json` | Report files that are missing or changed since the manifest was made. |
| `pngcheck FILE... --width W --height H [--dpi 300] [--no-alpha] [--allow-opaque-corners]` | Check PNG print files against **your** spec: dimensions, RGBA, DPI metadata, transparent corners, visible content. Technical checks only; it does not judge design quality. |

Exit code: `0` = success / verified, `1` = a check failed, `2` = usage error.

## Install and test

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Requires Python 3.10+.

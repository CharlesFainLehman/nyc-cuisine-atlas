"""Wrap web/index.html (authored as an artifact body) in a full HTML document for GitHub Pages."""
import hashlib
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB, DOCS = os.path.join(ROOT, "web"), os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

body = open(os.path.join(WEB, "index.html"), encoding="utf-8").read()
body = body.replace('<meta charset="utf-8">\n', "", 1)
head, _, rest = body.partition("</style>")
page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>body {{ margin: 0; }} img {{ max-width: 100%; }}</style>
{head}</style>
</head>
<body>
{rest.strip()}
</body>
</html>
"""
# Version data URLs by content hash so browsers never pair new page code with stale cached data.
for f in ("data.json", "boroughs.json", "neighborhoods.json"):
    shutil.copy(os.path.join(WEB, f), os.path.join(DOCS, f))
    v = hashlib.md5(open(os.path.join(WEB, f), "rb").read()).hexdigest()[:8]
    assert page.count(f'fetch("{f}")') == 1, f
    page = page.replace(f'fetch("{f}")', f'fetch("{f}?v={v}")')
open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8").write(page)
open(os.path.join(DOCS, ".nojekyll"), "w").close()
print("wrote docs/")

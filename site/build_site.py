"""Build a static GitHub Pages site that runs the Streamlit app in the browser (stlite + Pyodide).

    python site/build_site.py      # writes ./_site

The browser build runs in rules + register mode: an API key cannot be kept
secret on a public static page, so the Claude layer stays off there.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
STLITE = "1.9.2"

APP_FILES = ["app.py", "analyzer.py", "rules.py", "commitments.py", "completeness.py", "data_loader.py",
             "commitment_register.json", ".streamlit/config.toml"]
# pdfplumber depends on pypdfium2 (native), which Pyodide cannot install; PDF upload is server-only.
REQUIREMENTS = ["pandas", "scikit-learn", "python-docx"]

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AtliQ Contract Risk Analyzer</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@stlite/browser@{ver}/build/stlite.css" />
  <style>#boot{{font-family:system-ui,sans-serif;max-width:640px;margin:15vh auto;padding:0 16px;color:#333}}</style>
</head>
<body>
  <div id="boot"><h2>AtliQ Contract Risk Analyzer</h2>
  <p>Loading Python in your browser. The first visit takes about a minute; later visits are faster.</p>
  <p style="color:#777">Synthetic dataset · rules + commitment register mode · not legal advice.</p></div>
  <div id="root"></div>
  <script type="module">
    import {{ mount }} from "https://cdn.jsdelivr.net/npm/@stlite/browser@{ver}/build/stlite.js";
    document.getElementById("boot").remove();
    mount({{
      entrypoint: "app.py",
      requirements: {reqs},
      files: {files},
      env: {{ ATLIQ_BROWSER_BUILD: "1" }}
    }}, document.getElementById("root"));
  </script>
</body>
</html>
"""


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    rel_paths = list(APP_FILES) + sorted(str(p.relative_to(ROOT)) for p in (ROOT / "data").rglob("*") if p.is_file() and p.name != ".DS_Store")
    files = {}
    for rel in rel_paths:
        src = ROOT / rel
        dest_rel = rel.replace(".streamlit/", "streamlit-config/")  # GitHub Pages skips dot-folders without .nojekyll; keep it simple
        dest = OUT / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        files[rel] = {"url": dest_rel}
    (OUT / "index.html").write_text(PAGE.format(ver=STLITE, reqs=json.dumps(REQUIREMENTS), files=json.dumps(files, indent=2)), encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    print(f"Built {OUT} with {len(files)} files")


if __name__ == "__main__":
    main()

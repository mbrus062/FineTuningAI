#!/usr/bin/env python3
import os, json, sqlite3
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Body

from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

APP_DIR = Path("/home/mario/FineTuningAI/bookshelf_app")
DB_PATH = APP_DIR / "catalog.sqlite"
OVERRIDES_PATH = APP_DIR / "overrides.json"

HOST = "127.0.0.1"
PORT = 8787

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_DIR = APP_DIR / "ui"
if not UI_DIR.is_dir():
    raise RuntimeError(f"UI_DIR missing: {UI_DIR}")
app.mount("/_bookshelf", StaticFiles(directory=str(UI_DIR), html=True), name="bookshelf_ui")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_overrides():
    try:
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except FileNotFoundError:
        return {}


def save_overrides(data):
    tmp = str(OVERRIDES_PATH) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OVERRIDES_PATH)


UI_HTML = r"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Bookshelf (PDF)</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f7f7f7; }
  header { position: sticky; top: 0; background: white; padding: 12px 14px; border-bottom: 1px solid #ddd; z-index: 5; }
  #q { width: min(900px, 96vw); font-size: 16px; padding: 10px 12px; border: 1px solid #ccc; border-radius: 10px; }
  #meta { margin-top: 8px; color: #666; font-size: 13px; }
  main { padding: 14px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(56px, 56px)); gap: 10px; align-items: end; }
  .spine {
    width: 56px; height: 260px;
    border-radius: 10px;
    background: linear-gradient(180deg, rgba(255,255,255,.35), rgba(0,0,0,.08));
    box-shadow: 0 6px 16px rgba(0,0,0,.12);
    position: relative;
    cursor: pointer;
    overflow: hidden;
    border: 1px solid rgba(0,0,0,.08);
  }
  .spine:hover { transform: translateY(-2px); transition: .1s; }
  .label {
    position: absolute; left: 6px; right: 6px; bottom: 8px;
    writing-mode: vertical-rl;
    transform: rotate(180deg);
    font-size: 12px;
    line-height: 1.05;
    color: rgba(0,0,0,.85);
    text-overflow: ellipsis;
    overflow: hidden;
    max-height: 235px;
    user-select: none;
  }
  .edit {
    position: absolute; top: 8px; right: 8px;
    background: rgba(255,255,255,.75);
    border: 1px solid rgba(0,0,0,.12);
    border-radius: 8px;
    padding: 2px 6px;
    font-size: 12px;
  }
  .sentinel { height: 30px; }
  .modal {
    position: fixed; inset: 0;
    display: none; align-items: center; justify-content: center;
    background: rgba(0,0,0,.35);
    z-index: 20;
  }
  .card {
    width: min(720px, 92vw);
    background: white; border-radius: 14px; padding: 14px;
    box-shadow: 0 16px 40px rgba(0,0,0,.25);
  }
  .row { display: flex; gap: 10px; align-items: center; }
  .row input { flex: 1; font-size: 16px; padding: 10px 12px; border: 1px solid #ccc; border-radius: 10px; }
  .btn { padding: 10px 12px; border-radius: 10px; border: 1px solid #ccc; background: #f5f5f5; cursor: pointer; }
  .btn.primary { background: #111; color: white; border-color: #111; }
  .hint { margin-top: 8px; color: #666; font-size: 13px; }
</style>
</head>
<body>
<header>
  <input id="q" placeholder="Search title/path…" />
  <div id="meta"></div>
</header>

<main>
  <div class="grid" id="grid"></div>
  <div class="sentinel" id="sentinel"></div>
</main>

<div class="modal" id="modal">
  <div class="card">
    <div style="font-weight:700; font-size:16px; margin-bottom:10px;">Edit spine title</div>
    <div class="row">
      <input id="editTitle" />
      <button class="btn" id="cancel">Cancel</button>
      <button class="btn primary" id="save">Save</button>
    </div>
    <div class="hint">Tip: keep it short for cleaner spines.</div>
  </div>
</div>

<script>
let q = "";
let offset = 0;
let limit = 240;
let loading = false;
let done = false;
let total = 0;
let lastQuery = "";
let editId = null;

const grid = document.getElementById("grid");
const meta = document.getElementById("meta");
const sentinel = document.getElementById("sentinel");

const modal = document.getElementById("modal");
const editTitle = document.getElementById("editTitle");
document.getElementById("cancel").onclick = () => { modal.style.display="none"; editId=null; };
document.getElementById("save").onclick = async () => {
  const val = (editTitle.value || "").trim();
  if (!editId) return;
  await fetch("/api/override", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({id: editId, spine_title: val})
  });
  // refresh current view
  resetAndLoad();
  modal.style.display="none";
  editId=null;
};

function spineColorFromId(id){
  // deterministic-ish color palette via HSL
  let n = 0;
  for (let i=0;i<id.length;i++) n = (n*31 + id.charCodeAt(i)) >>> 0;
  const hue = n % 360;
  return `linear-gradient(180deg, hsla(${hue},70%,70%,0.9), hsla(${(hue+30)%360},70%,55%,0.95))`;
}

function makeSpine(item){
  const d = document.createElement("div");
  d.className = "spine";
  d.style.background = spineColorFromId(item.id);
  d.title = item.title + "\n" + item.pdf_path;

  const lab = document.createElement("div");
  lab.className = "label";
  lab.textContent = item.spine_title || item.title;

  const ed = document.createElement("div");
  ed.className = "edit";
  ed.textContent = "✎";
  ed.onclick = (ev) => {
    ev.stopPropagation();
    editId = item.id;
    editTitle.value = item.spine_title || item.title || "";
    modal.style.display = "flex";
    editTitle.focus();
    editTitle.select();
  };

  d.onclick = () => {
    window.open(`/view?id=${encodeURIComponent(item.id)}`, "_blank");
  };

  d.appendChild(ed);
  d.appendChild(lab);
  return d;
}

async function loadMore(){
  if (loading || done) return;
  loading = true;

  const resp = await fetch(`/api/catalog?q=${encodeURIComponent(q)}&offset=${offset}&limit=${limit}`);
  const data = await resp.json();
  total = data.total;

  meta.textContent = `Showing ${Math.min(offset + data.items.length, total)} of ${total} PDFs`;

  for (const it of data.items) grid.appendChild(makeSpine(it));

  offset += data.items.length;
  if (offset >= total || data.items.length === 0) done = true;
  loading = false;
}

function resetAndLoad(){
  grid.innerHTML = "";
  offset = 0;
  done = false;
  loadMore();
}

const io = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (e.isIntersecting) loadMore();
  }
});
io.observe(sentinel);

document.getElementById("q").addEventListener("input", (ev) => {
  q = ev.target.value || "";
  if (q === lastQuery) return;
  lastQuery = q;
  // debounce
  clearTimeout(window.__t);
  window.__t = setTimeout(resetAndLoad, 200);
});

// initial
resetAndLoad();
</script>
</body>
</html>
"""

class OverrideIn(BaseModel):
    id: str
    spine_title: str | None = None
    title: str | None = None

@app.get("/")
def home():
    return RedirectResponse(url="/_bookshelf/")

@app.get("/api/catalog")
def catalog(q: str = Query(default=""), offset: int = 0, limit: int = 200):
    q = (q or "").strip()
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    conn = db()
    try:
        if q:
            like = f"%{q}%"
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM pdfs WHERE title LIKE ? OR spine_title LIKE ? OR pdf_path LIKE ?",
                (like, like, like),
            ).fetchone()["c"]
            rows = conn.execute(
                "SELECT id, pdf_path, title, spine_title FROM pdfs WHERE title LIKE ? OR spine_title LIKE ? OR pdf_path LIKE ? "
                "ORDER BY title LIMIT ? OFFSET ?",
                (like, like, like, limit, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) AS c FROM pdfs").fetchone()["c"]
            rows = conn.execute(
                "SELECT id, pdf_path, title, spine_title FROM pdfs ORDER BY title LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()

        items = [dict(r) for r in rows]
        return {"total": total, "items": items}
    finally:
        conn.close()

@app.get("/api/index")
def api_index():
    """
    Compatibility endpoint for the shelf UI that expects /api/index.
    Returns {"entries":[...]} similar to the older index.json structure.
    """
    conn = db()
    try:
        rows = conn.execute(
            "SELECT id, pdf_path, title, spine_title, mtime, size FROM pdfs ORDER BY title"
        ).fetchall()

        entries = []
        for r in rows:
            entry = {
                "id": r["id"],
                "rel_path": r["pdf_path"],  # UI often calls it rel_path
                "pdf_path": r["pdf_path"],
                "title": r["title"],
                "spine_title": r["spine_title"],
                "mtime": r["mtime"],
                "size": r["size"],
                # placeholders (until we add real columns)
                "author": "",
                "language": "",
                "source": "",
                "tradition": "",
                "status": "pdf",
            }

            # Apply overrides.json (keyed by absolute pdf_path)
            ov = load_overrides().get(entry["pdf_path"], {})
            if ov.get("hidden") is True:
                continue
            if (ov.get("title") or "").strip():
                entry["title"] = ov["title"].strip()
                entry["spine_title"] = ov["title"].strip()
            if ov.get("author") is not None and ov.get("author") != "":
                entry["author"] = ov["author"]

            entries.append(entry)
        return {"entries": entries}
    finally:
        conn.close()

@app.get("/api/pdf")
def pdf(id: str):
    conn = db()
    try:
        row = conn.execute("SELECT pdf_path FROM pdfs WHERE id=?", (id,)).fetchone()
        if not row:
            raise HTTPException(404, "Unknown id")

        p = row["pdf_path"]
        if not os.path.isfile(p):
            raise HTTPException(404, "File missing")

        resp = FileResponse(
            p, media_type="application/pdf", filename=os.path.basename(p)
        )
        resp.headers["Content-Disposition"] = (
            f'inline; filename="{os.path.basename(p)}"'
        )
        return resp

    finally:
        conn.close()


@app.post("/api/override")
def override(data: OverrideIn):
    conn = db()
    try:
        row = conn.execute(
            "SELECT id, title, spine_title FROM pdfs WHERE id=?", (data.id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Unknown id")
    finally:
        conn.close()

    overrides = load_overrides()
    overrides.setdefault(data.id, {})
    if data.spine_title is not None:
        overrides[data.id]["spine_title"] = data.spine_title
    if data.title is not None:
        overrides[data.id]["title"] = data.title
    save_overrides(overrides)

    # also persist into sqlite immediately for fast display
    conn = db()
    try:
        if data.spine_title is not None:
            conn.execute(
                "UPDATE pdfs SET spine_title=? WHERE id=?", (data.spine_title, data.id)
            )
        if data.title is not None:
            conn.execute("UPDATE pdfs SET title=? WHERE id=?", (data.title, data.id))
        conn.commit()
    finally:
        conn.close()

    return JSONResponse({"ok": True})


from fastapi.responses import HTMLResponse  # (already imported in your file)
import bookshelf_overrides as bsov


@app.get("/view", response_class=HTMLResponse)
def view(id: str):
    # simple inline PDF viewer wrapper
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<title>PDF Viewer</title>
<style>html,body{{margin:0;height:100%;}} iframe{{border:0;width:100%;height:100%;}}</style>
</head>
<body>
<iframe src="/api/pdf?id={id}"></iframe>
</body></html>"""


@app.post("/api/override_path")
def api_override_path(payload: dict = Body(...)):
    """
    Payload: {"path": "...pdf", "title": "...", "author": "...", "hidden": true|false, "clear": true|false}
    Keyed by absolute PDF path.
    """
    return bsov.update_override(
        path=payload.get("path"),
        title=payload.get("title") if "title" in payload else None,
        author=payload.get("author") if "author" in payload else None,
        hidden=payload.get("hidden") if "hidden" in payload else None,
        clear=bool(payload.get("clear")),
    )

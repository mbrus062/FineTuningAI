#!/usr/bin/env python3
import os
import html
import mimetypes
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler, HTTPServer

LIBRARY_ROOT = os.path.expanduser("~/FineTuningAI/library")
HOST = "127.0.0.1"
PORT = 8787

def safe_join(root, rel_path):
    rel_path = rel_path.lstrip("/")
    rel_path = os.path.normpath(rel_path)
    full = os.path.abspath(os.path.join(root, rel_path))
    root_abs = os.path.abspath(root)
    if not full.startswith(root_abs):
        raise ValueError("Unsafe path")
    return full

def list_dir(full_path):
    entries = []
    with os.scandir(full_path) as it:
        for entry in it:
            if entry.name.startswith("."):
                continue
            if entry.is_file():
                if not entry.name.lower().endswith(".pdf"):
                    continue
            entries.append(entry)
    entries.sort(key=lambda e: (not e.is_dir(), e.name.lower()))
    return entries

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            path = unquote(self.path.split("?", 1)[0])
            if path == "/":
                rel = ""
            else:
                rel = path

            full = safe_join(LIBRARY_ROOT, rel)

            if os.path.isdir(full):
                self.serve_directory(full, rel)
            elif os.path.isfile(full) and full.lower().endswith(".pdf"):
                self.serve_file(full)
            else:
                self.send_error(404, "Not found")
        except ValueError:
            self.send_error(400, "Bad request")

    def serve_directory(self, full_path, rel_path):
        entries = list_dir(full_path)

        lines = []
        lines.append("<!doctype html><html><head>")
        lines.append('<meta charset="utf-8">')
        lines.append("<title>Bookshelf</title>")
        lines.append("""
<style>
body { font-family: sans-serif; margin: 24px; }
h1 { margin-bottom: 8px; }
ul { list-style: none; padding-left: 0; }
li { margin: 6px 0; }
a { text-decoration: none; }
a:hover { text-decoration: underline; }
.dir { font-weight: bold; }
</style>
""")
        lines.append("</head><body>")
        lines.append(f"<h1>Bookshelf</h1>")
        lines.append("<ul>")

        if rel_path and rel_path != "/":
            parent = os.path.dirname(rel_path.rstrip("/"))
            if not parent.startswith("/"):
                parent = "/" + parent if parent else "/"
            lines.append(f"<li><a class='dir' href='{parent}'>⬅ Up</a></li>")

        for e in entries:
            name = e.name
            if e.is_dir():
                href = rel_path.rstrip("/") + "/" + name
                if not href.startswith("/"):
                    href = "/" + href
                lines.append(f"<li>📁 <a class='dir' href='{href}'>{name}/</a></li>")
            else:
                href = rel_path.rstrip("/") + "/" + name
                if not href.startswith("/"):
                    href = "/" + href
                lines.append(f"<li>📄 <a href='{href}'>{name}</a></li>")

        lines.append("</ul>")
        lines.append("</body></html>")
        data = "\n".join(lines).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_file(self, full_path):
        ctype, _ = mimetypes.guess_type(full_path)
        ctype = ctype or "application/pdf"

        try:
            with open(full_path, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(500, "Could not read file")
            return

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def main():
    os.makedirs(LIBRARY_ROOT, exist_ok=True)
    httpd = HTTPServer((HOST, PORT), Handler)
    print(f"Bookshelf running at http://{HOST}:{PORT}")
    httpd.serve_forever()

if __name__ == "__main__":
    main()

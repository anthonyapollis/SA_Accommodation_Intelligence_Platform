import os, http.server, functools
os.chdir(os.path.dirname(os.path.abspath(__file__)))
port = int(os.environ.get("PORT", 8773))
handler = http.server.SimpleHTTPRequestHandler
httpd = http.server.HTTPServer(("", port), handler)
print(f"Serving on http://localhost:{port}")
httpd.serve_forever()

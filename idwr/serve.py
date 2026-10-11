"""Local-only dashboard with an explicit, same-origin data update button."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from threading import Lock
import json
import webbrowser
from urllib.parse import urlsplit
from .update import ROOT, JST, run

LOCK = Lock()

def allowed_update(headers, port):
    origin = f'http://127.0.0.1:{port}'
    return (headers.get('Host') == f'127.0.0.1:{port}'
            and headers.get('Origin') == origin
            and headers.get('X-IDWR-Update') == '1')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'public'), **kwargs)
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
    def reply(self, code, value):
        raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if urlsplit(self.path).path == '/api/capabilities':
            self.reply(200, {'update': True})
        else:
            super().do_GET()
    def do_POST(self):
        if self.path != '/api/update':
            return self.reply(404, {'error': 'Not found'})
        if not allowed_update(self.headers, self.server.server_port):
            return self.reply(403, {'error': '同じ画面からの更新操作のみ受け付けます'})
        if not LOCK.acquire(blocking=False):
            return self.reply(409, {'error': '別の更新処理が進行中です'})
        try:
            data = run(list(range(2025, datetime.now(JST).year + 1)))
            self.reply(200, {'latest': data['latest'], 'checked_at': data['last_checked_at']})
        except Exception as exc:
            self.reply(502, {'error': f'更新失敗：{exc}。表示データは保持しています。'})
        finally:
            LOCK.release()

def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'更新ボタン付き画面：{url}\n終了するときはこのウィンドウを閉じてください。', flush=True)
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()

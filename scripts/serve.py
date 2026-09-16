import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/'dist'

class Handler(SimpleHTTPRequestHandler):
    def send_error(self,code,message=None,explain=None):
        if code==404 and (ROOT/'404.html').exists():
            body=(ROOT/'404.html').read_bytes()
            self.send_response(404)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            if self.command!='HEAD':self.wfile.write(body)
        else:super().send_error(code,message,explain)

parser=argparse.ArgumentParser()
parser.add_argument('--port',type=int,default=4173)
args=parser.parse_args()
server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(ROOT)))
print(f'Серебряный полоз: http://127.0.0.1:{args.port}/',flush=True)
try:server.serve_forever()
except KeyboardInterrupt:server.server_close()

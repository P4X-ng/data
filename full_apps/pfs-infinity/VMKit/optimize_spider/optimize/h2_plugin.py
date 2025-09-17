from hypercorn.config import Config
from hypercorn.asyncio import serve
from fastapi import FastAPI

class HTTP2MultiplexingPlugin:
    def __init__(self, app: FastAPI):
        self.app = app

    def start_http2_server(self, app, host="0.0.0.0", port=8080):
        config = Config()
        config.bind = [f"{host}:{port}"]
        config.alpn_protocols = ["h2"]  # Enable HTTP/2
        
        # Use Hypercorn to serve with HTTP/2
        return serve(app, config)

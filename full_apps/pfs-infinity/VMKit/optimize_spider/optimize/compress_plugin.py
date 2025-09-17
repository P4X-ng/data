import brotli
import gzip
from fastapi import Request, Response
import torch

class CompressionPlugin:
    def __init__(self):
        pass
    
    def compress_data(self, data, method='brotli'):
        if method == 'brotli':
            # Using Brotli compression
            return brotli.compress(data)
        elif method == 'gzip':
            # Using Gzip compression
            return gzip.compress(data)
        else:
            raise ValueError(f"Unknown compression method: {method}")

    async def handle_request(self, request: Request, response: Response):
        data = await request.body()

        # Use GPU for intensive compression tasks
        if torch.cuda.is_available():
            compressed_data = self.compress_data(data, method='brotli')  # Using Brotli by default
        else:
            compressed_data = self.compress_data(data, method='gzip')  # Fallback to Gzip if no GPU

        response.body = compressed_data
        response.headers['Content-Encoding'] = 'br' if 'brotli' in request.headers.get('Accept-Encoding', '') else 'gzip'
        return response

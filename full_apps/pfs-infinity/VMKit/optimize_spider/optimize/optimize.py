import socket
from urllib.parse import unquote
from fastapi import FastAPI, Request, Response

app = FastAPI()

@app.route("/{full_path:path}", methods=["CONNECT"])
async def handle_connect(request: Request, full_path: str):
    # Decode the URL (for example, converting %3A to :)
    full_path_decoded = unquote(full_path)

    # Extract the host and port
    try:
        host, port = full_path_decoded.split(":")
        port = int(port)
    except ValueError:
        return Response(content="Invalid CONNECT request format", status_code=400)

    # Create a connection to the target server
    try:
        upstream = socket.create_connection((host, port))

        # Send the 200 Connection Established response back to the client
        client_connection = request.scope["client"]
        client_socket = client_connection[1]
        client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

        # Start tunneling traffic between the client and the upstream server
        while True:
            # Read from client and forward to upstream
            data_from_client = client_socket.recv(4096)
            if not data_from_client:
                break
            upstream.sendall(data_from_client)

            # Read from upstream and forward to client
            data_from_upstream = upstream.recv(4096)
            if not data_from_upstream:
                break
            client_socket.sendall(data_from_upstream)

    except Exception as e:
        return Response(content=f"Failed to establish connection: {str(e)}", status_code=500)

    finally:
        upstream.close()

    return Response(content="Connection closed", status_code=200)

if __name__ == "__main__":
    hypercorn optimize:app --bind 0.0.0.0:8888 --workers 8

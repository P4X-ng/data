import socket
from fastapi import FastAPI, Request, Response

app = FastAPI()

@app.route("/{full_path:path}", methods=["CONNECT"])
async def handle_connect(request: Request, full_path: str):
    # Extract the host and port from the request URL
    host, port = full_path.split(":")
    port = int(port)

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

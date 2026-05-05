import select
import socket
import threading

LISTEN = ("0.0.0.0", 18602)
TARGET = ("127.0.0.1", 18601)


def pipe(left: socket.socket, right: socket.socket) -> None:
    try:
        while True:
            readable, _, _ = select.select([left, right], [], [], 60)
            for sock in readable:
                data = sock.recv(65536)
                if not data:
                    return
                (right if sock is left else left).sendall(data)
    except Exception:
        pass
    finally:
        left.close()
        right.close()


def handle(client: socket.socket) -> None:
    try:
        target = socket.create_connection(TARGET, timeout=10)
        pipe(client, target)
    except Exception:
        client.close()


server = socket.socket()
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(LISTEN)
server.listen(100)
print("yaobi_port_forward_18602 ready", flush=True)

while True:
    client, _ = server.accept()
    threading.Thread(target=handle, args=(client,), daemon=True).start()

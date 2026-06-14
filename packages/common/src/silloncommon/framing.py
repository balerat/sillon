import struct

def send_msg(sock, data: bytes) -> None:
    """Send a length-prefixed message."""
    length = struct.pack(">I", len(data)) # 4-byte big endian
    sock.sendall(length + data)

def recv_msg(sock) -> bytes | None:
    """Receive a length-prefixed. Returns None if connection closed."""
    header = _recv_exact(sock, 4)
    if header is None:
        return None
    length = struct.unpack(">I", header)[0]
    return _recv_exact(sock, length)

def _recv_exact(sock, n: int) -> bytes | None:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


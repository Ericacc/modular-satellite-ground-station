import socketserver
import threading

from aegissat.protocol.ipc import TYPE_TELEMETRY, extract_messages


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        buffer = b""
        while True:
            chunk = self.request.recv(4096)
            if not chunk:
                break
            messages, buffer = extract_messages(buffer + chunk)
            for message in messages:
                if message["type"] == TYPE_TELEMETRY:
                    self.server.telemetry_service.process_payload(
                        message["payload"], "tcp", f"tcp-{message['sequence']}"
                    )


class TelemetryTCPServer:
    def __init__(self, telemetry_service, host="127.0.0.1", port=9000):
        self.server = socketserver.ThreadingTCPServer((host, port), _Handler)
        self.server.daemon_threads = True
        self.server.telemetry_service = telemetry_service
        self.thread = None

    @property
    def address(self):
        return self.server.server_address

    def start(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2)

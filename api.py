from http.server import BaseHTTPRequestHandler, HTTPServer
import json


class ImpactAPI(BaseHTTPRequestHandler):

    def send_json(self, data):
        response = json.dumps(data).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()

        self.wfile.write(response)

    def do_GET(self):

        if self.path == "/":
            self.send_json({
                "message": "Impact.AI Backend is running",
                "status": "online"
            })

        elif self.path == "/health":
            self.send_json({
                "status": "healthy"
            })

        else:
            self.send_response(404)
            self.send_json({
                "error": "Endpoint not found"
            })


server = HTTPServer(
    ("127.0.0.1", 8000),
    ImpactAPI
)

print("===================================")
print("   Impact.AI Backend")
print("   Server running successfully")
print("   http://127.0.0.1:8000")
print("===================================")

server.serve_forever()
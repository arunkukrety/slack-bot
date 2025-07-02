"""
Health check endpoint for Vercel deployment
"""
from http.server import BaseHTTPRequestHandler
import json
import time

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests for health check"""
        health_data = {
            "status": "healthy",
            "timestamp": time.time(),
            "service": "slack-bot-vercel",
            "platform": "vercel-serverless"
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(health_data).encode())
        return

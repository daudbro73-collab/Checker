from pyngrok import ngrok
import time
import os
import signal
import sys

# Close all tunnels first
ngrok.kill()

# Open HTTP tunnel
# Use 'http' and port 8003
try:
    http_tunnel = ngrok.connect(8003, bind_tls=True)
    print(f"Ngrok Tunnel URL: {http_tunnel.public_url}")
except Exception as e:
    print(f"Error starting ngrok: {e}")
    sys.exit(1)

# Keep alive
def signal_handler(sig, frame):
    print("Stopping ngrok...")
    ngrok.kill()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
print("Press Ctrl+C to stop")
signal.pause()

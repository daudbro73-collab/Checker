import subprocess
import time
import re
import os
import signal
import sys
import threading

# Configuration
BACKEND_PORT = 8003
BOT_SCRIPT = "bot.py"
BACKEND_CMD = f"/Users/rustamberheev/Desktop/AML/venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port {BACKEND_PORT}"
SSH_CMD = f"ssh -o StrictHostKeyChecking=no -R aml-guard-rustam:80:127.0.0.1:{BACKEND_PORT} serveo.net"
PYTHON_EXEC = "/Users/rustamberheev/Desktop/AML/venv/bin/python3"

# Global processes
backend_process = None
tunnel_process = None
bot_process = None
current_url = None
running = True

def log(msg):
    print(f"[AutoRun] {msg}")

def start_backend():
    global backend_process
    log("Starting Backend...")
    # Add a delay and restart logic if backend fails
    backend_process = subprocess.Popen(BACKEND_CMD.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)

def update_bot_url(url):
    try:
        with open(BOT_SCRIPT, 'r') as f:
            content = f.read()
        
        # Regex to find WEBAPP_URL = "..."
        new_content = re.sub(
            r'WEBAPP_URL = "https://[^"]+"',
            f'WEBAPP_URL = "{url}/webapp"',
            content
        )
        
        if content != new_content:
            with open(BOT_SCRIPT, 'w') as f:
                f.write(new_content)
            log(f"Updated bot.py with new URL: {url}")
            return True
        return False
    except Exception as e:
        log(f"Error updating bot.py: {e}")
        return False

def start_bot():
    global bot_process
    if bot_process:
        log("Stopping old bot instance...")
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except:
            bot_process.kill()
    
    log("Starting Bot...")
    bot_process = subprocess.Popen([PYTHON_EXEC, BOT_SCRIPT])

def monitor_tunnel():
    global tunnel_process, current_url, running
    
    while running:
        log("Starting SSH Tunnel to serveo.net (trying fixed subdomain)...")
        tunnel_process = subprocess.Popen(
            SSH_CMD.split(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        url_found = False
        
        # Read output line by line to find URL
        while True:
            line = tunnel_process.stdout.readline()
            if not line:
                break
            
            # log(f"Tunnel: {line.strip()}") # Debug
            
            # Serveo Output: "Forwarding HTTP traffic from https://aml-guard-rustam.serveo.net"
            match = re.search(r'https://[a-zA-Z0-9-]+\.serveo\.net', line)
            # Or localhost.run fallback if serveo fails later (but we force serveo now)
            # match = re.search(r'https://[a-zA-Z0-9-]+\.lhr\.life', line) 
            
            if match:
                new_url = match.group(0)
                if new_url != current_url:
                    current_url = new_url
                    log(f"*** NEW TUNNEL URL FOUND: {current_url} ***")
                    update_bot_url(current_url)
                    start_bot()
                url_found = True
            
            if tunnel_process.poll() is not None:
                log("Tunnel process ended unexpectedly.")
                break
        
        if running:
            log("Tunnel disconnected. Retrying in 5 seconds...")
            time.sleep(5)

def cleanup(signum, frame):
    global running
    log("Shutting down...")
    running = False
    if tunnel_process: tunnel_process.terminate()
    if bot_process: bot_process.terminate()
    if backend_process: backend_process.terminate()
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    # Kill any existing processes on port 8003 (optional but good)
    os.system(f"lsof -ti:{BACKEND_PORT} | xargs kill -9 2>/dev/null")
    
    start_backend()
    
    # Run tunnel monitor in main thread or separate? 
    # Since readline is blocking, let's run it here.
    try:
        monitor_tunnel()
    except KeyboardInterrupt:
        cleanup(None, None)

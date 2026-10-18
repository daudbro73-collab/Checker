import requests
import json

BASE_URL = "http://localhost:8002"

def test_register():
    email = "test@example.com"
    password = "password123"
    
    print(f"Registering {email}...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={
            "email": email,
            "password": password
        })
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
        
        if resp.status_code == 200:
            token = resp.json()["access_token"]
            print("Token obtained.")
            return token
        else:
            print("Registration failed.")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    test_register()

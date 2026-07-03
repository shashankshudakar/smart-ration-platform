import uvicorn
import os
from dotenv import load_dotenv

# Explicitly load .env from the current folder
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

if __name__ == "__main__":
    # Default to 8000 as defined in your .env
    port = int(os.getenv("PORT", 8000))
    print(f"\nSmart Ration Python Backend")
    print(f"Port: {port}")
    print(f"URL: http://localhost:{port}\n")
    uvicorn.run("app.main:socket_app", host="0.0.0.0", port=port, reload=True)

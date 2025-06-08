from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import time
from jose import jwt
from typing import Optional

app = FastAPI()

# Add CORS to allow requests from any origin (for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API keys from environment variables
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_SECRET = os.environ.get("LIVEKIT_SECRET")

@app.get("/api/token-health")
async def health_check():
    """Health check endpoint to verify the service is running"""
    keys_configured = LIVEKIT_API_KEY is not None and LIVEKIT_SECRET is not None
    return {
        "status": "healthy",
        "keys_configured": keys_configured
    }

@app.get("/api/get-token")
async def get_token(user_id: str, room_name: Optional[str] = None):
    """Generate a LiveKit JWT token for the specified user and room"""
    try:
        if not LIVEKIT_API_KEY or not LIVEKIT_SECRET:
            raise HTTPException(status_code=500, detail="LiveKit API keys not configured")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
        
        # Use provided room name or default to "voice-room"
        room = room_name if room_name else "voice-room"
        
        # Create token with 24 hour validity
        expiration = int(time.time()) + 86400  # 24 hours
        
        # Define the token claims
        claims = {
            "sub": user_id,
            "iss": LIVEKIT_API_KEY,
            "nbf": int(time.time()),
            "exp": expiration,
            "video": {
                "room": room,
                "roomJoin": True,
                "canPublish": True,
                "canSubscribe": True,
                "canPublishData": True
            }
        }
        
        # Create the JWT token
        token = jwt.encode(claims, LIVEKIT_SECRET, algorithm="HS256")
        
        return {"token": token, "room": room}
    
    except Exception as e:
        print(f"Error generating token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

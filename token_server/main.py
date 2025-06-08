from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import jwt
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
import os
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the FastAPI app
app = FastAPI(
    title="LiveKit Token Server",
    description="Service for generating secure LiveKit access tokens",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Read secrets from environment variables or mounted files (GCP Secret Manager)
def read_secret(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None
        
LIVEKIT_API_KEY = read_secret("/secrets/LIVEKIT_API_KEY") or os.getenv("LIVEKIT_API_KEY")
LIVEKIT_SECRET = read_secret("/secrets/LIVEKIT_SECRET") or os.getenv("LIVEKIT_SECRET")

# Verify configuration at startup
if not LIVEKIT_API_KEY or not LIVEKIT_SECRET:
    logger.warning("LiveKit API key or secret is not configured. Token generation will fail.")

def validate_config():
    """Validate that the LiveKit configuration is available"""
    if not LIVEKIT_API_KEY or not LIVEKIT_SECRET:
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail="LiveKit is not properly configured on the server"
        )
    return True

def create_token(identity: str, room: str, ttl_seconds: int = 3600):
    """Create a LiveKit access token
    
    Args:
        identity: User identifier
        room: Room name to join
        ttl_seconds: Token validity period in seconds (default: 1 hour)
        
    Returns:
        JWT token string
    """
    try:
        now = int(time.time())
        payload = {
            "jti": f"{identity}-{now}",
            "iss": LIVEKIT_API_KEY,
            "sub": identity,
            "nbf": now,
            "exp": now + ttl_seconds,
            "video": {
                "room_join": True,
                "room": room,
                "can_publish": True,
                "can_subscribe": True
            }
        }
        return jwt.encode(payload, LIVEKIT_SECRET, algorithm="HS256")
    except Exception as e:
        logger.error(f"Error creating token: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate token: {str(e)}"
        )

@app.get("/get-token")
def get_token(
    identity: str = Query(..., description="User identifier"),
    room: str = Query(..., description="Room name to join"),
    _: bool = Depends(validate_config)
):
    """Generate a LiveKit access token for a user to join a room"""
    try:
        token = create_token(identity, room)
        return {"token": token, "identity": identity, "room": room}
    except Exception as e:
        logger.error(f"Error in get_token: {str(e)}")
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
        
@app.get("/health")
async def health_check():
    """Check if the token server is properly configured"""
    return {
        "status": "ok" if LIVEKIT_API_KEY and LIVEKIT_SECRET else "misconfigured",
        "configured": bool(LIVEKIT_API_KEY and LIVEKIT_SECRET)
    }

from fastapi import FastAPI, Response, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import json
import google.generativeai as genai
from typing import Dict, Any, AsyncIterator, Literal, Optional
import asyncio

app = FastAPI()

# Add CORS middleware to allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Read API keys from environment variables
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Configure the Gemini API
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def classify_intent(message: str) -> Literal['medical', 'general']:
    medical_keywords = ['diabetes', 'asthma', 'cancer', 'pregnancy', 'treatment', 'symptom']
    return 'medical' if any(word in message.lower() for word in medical_keywords) else 'general'

async def query_gemini_flash(message: str) -> AsyncIterator[str]:
    """Query Gemini Flash model for general conversational responses"""
    try:
        if not GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not configured")
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(message, stream=True)
        
        async for chunk in response:
            if hasattr(chunk, 'text') and chunk.text:
                yield chunk.text
    except Exception as e:
        print(f"Error querying Gemini Flash: {e}")
        # Fallback response in case of error
        yield "I'm sorry, I couldn't process that request. Please try again later."

async def query_gemini_med(message: str) -> AsyncIterator[str]:
    """Query Gemini model with medical context for healthcare-related questions"""
    try:
        if not GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY not configured")
        
        # Using a more capable model for medical questions
        model = genai.GenerativeModel('gemini-1.5-pro')
        med_prompt = f"""You are MedGemma, a helpful medical assistant AI. 
        Please provide a thoughtful response to the following health question:
        {message}
        
        Always mention that you're an AI and not a doctor, and the user should consult healthcare professionals.
        """
        response = await model.generate_content_async(med_prompt, stream=True)
        
        async for chunk in response:
            if hasattr(chunk, 'text') and chunk.text:
                yield chunk.text
    except Exception as e:
        print(f"Error querying Gemini Med: {e}")
        # Fallback response in case of error
        yield "I'm sorry, I couldn't process that medical request. Please try again later."

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify the service is running"""
    return {"status": "healthy"}

@app.post("/api/stream")
async def stream_response(request: Request, response: Response):
    """Stream AI response based on user message intent"""
    try:
        data = await request.json()
        message = data.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="No message provided")
        
        intent = classify_intent(message)
        
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        
        # Select the appropriate model based on intent
        if intent == 'medical':
            async for token in query_gemini_med(message):
                yield f"data: {json.dumps({'token': token})}\n\n"
        else:
            async for token in query_gemini_flash(message):
                yield f"data: {json.dumps({'token': token})}\n\n"
    
    except Exception as e:
        print(f"Error in stream_response: {e}")
        yield f"data: {json.dumps({'token': 'Error: Could not process your request.'})}\n\n"

@app.post("/api/tts")
async def text_to_speech(request: Request):
    """Convert text to speech using ElevenLabs API"""
    try:
        data = await request.json()
        text = data.get("text", "")
        
        if not text:
            raise HTTPException(status_code=400, detail="No text provided")
        
        if not ELEVENLABS_API_KEY:
            raise HTTPException(status_code=500, detail="ElevenLabs API key not configured")
        
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM/stream"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        tts_response = requests.post(url, json=data, headers=headers, stream=True)
        
        if tts_response.status_code != 200:
            raise HTTPException(status_code=tts_response.status_code, 
                              detail=f"ElevenLabs API error: {tts_response.text}")
        
        return Response(
            content=tts_response.content,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=speech.mp3"}
        )
    
    except Exception as e:
        print(f"Error in text_to_speech: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/deepgram-proxy")
async def deepgram_proxy(request: Request):
    """Proxy requests to Deepgram API to avoid exposing API key to frontend"""
    try:
        # Debug information
        print("Deepgram proxy called")
        content_type = request.headers.get("Content-Type", "audio/webm")
        print(f"Content-Type: {content_type}")
        
        if not DEEPGRAM_API_KEY:
            print("Deepgram API key not configured")
            raise HTTPException(status_code=500, detail="Deepgram API key not configured")
            
        # Get the request body
        body = await request.body()
        print(f"Request body size: {len(body)} bytes")
        
        if len(body) == 0:
            print("Empty request body")
            raise HTTPException(status_code=400, detail="No audio data provided")
        
        # Set up headers for Deepgram
        # Debug the API key format (showing only first 3 chars for security)
        if DEEPGRAM_API_KEY:
            key_prefix = DEEPGRAM_API_KEY[:3] if len(DEEPGRAM_API_KEY) > 3 else "[empty]"
            key_format = f"{key_prefix}...{len(DEEPGRAM_API_KEY)} chars"
            print(f"Using Deepgram API key format: {key_format}")
        
        # Deepgram's newer API keys don't require the 'Token ' prefix
        headers = {
            "Authorization": DEEPGRAM_API_KEY,  # Direct API key without 'Token ' prefix
            "Content-Type": content_type
        }
        print(f"Using direct authorization with key: '{DEEPGRAM_API_KEY[:3]}...'")


        
        # Call Deepgram API
        print("Calling Deepgram API...")
        dg_url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&filler_words=false"
        
        try:
            dg_response = requests.post(
                dg_url,
                data=body,
                headers=headers,
                timeout=10  # Add timeout to prevent hanging
            )
            
            print(f"Deepgram response status: {dg_response.status_code}")
            
            if dg_response.status_code != 200:
                print(f"Deepgram error: {dg_response.text}")
                raise HTTPException(status_code=dg_response.status_code, 
                                detail=f"Deepgram API error: {dg_response.text}")
                
            # Return the response from Deepgram
            return Response(
                content=dg_response.content,
                media_type="application/json"
            )
            
        except requests.exceptions.RequestException as req_err:
            print(f"Request exception: {req_err}")
            raise HTTPException(status_code=500, detail=f"Error connecting to Deepgram: {str(req_err)}")
    
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        print(f"Unexpected error in deepgram_proxy: {e}")
        import traceback
        traceback.print_exc()  # Print full traceback for debugging
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


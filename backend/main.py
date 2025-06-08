from fastapi import FastAPI, Request, WebSocket, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal, List, Dict, Any, Union
import asyncio
import time
import requests
import os
import json
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPIError

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Secrets from mounted files (GCP Secret Manager)
def read_secret(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

ELEVENLABS_API_KEY = read_secret("/secrets/ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_API_KEY", "")
DEEPGRAM_API_KEY = read_secret("/secrets/DEEPGRAM_API_KEY") or os.getenv("DEEPGRAM_API_KEY", "")
GEMINI_API_KEY = read_secret("/secrets/GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Default voice

# Configure Gemini API if key is available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def classify_intent(message: str) -> Literal['medical', 'general']:
    medical_keywords = ['diabetes', 'asthma', 'cancer', 'pregnancy', 'treatment', 'symptom', 'doctor', 'medicine', 
                      'hospital', 'health', 'pain', 'disease', 'diagnosis', 'medical', 'patient']
    return 'medical' if any(word in message.lower() for word in medical_keywords) else 'general'

async def query_gemini_flash(prompt: str) -> List[str]:
    try:
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured")
            
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        
        if not response.text:
            return ["I'm sorry,", " I", " couldn't", " generate", " a", " response.", " Please", " try", " again."]
        
        # Split response into tokens for streaming simulation
        words = response.text.split()
        tokens = []
        for word in words:
            tokens.append(word)
            tokens.append(" ")
        return tokens
        
    except (GoogleAPIError, ValueError) as e:
        # Fallback response if API fails
        return ["I'm", " having", " trouble", " connecting", " to", " my", " brain.", " Please", " try", " again."]

async def query_medgemma(prompt: str) -> List[str]:
    try:
        if not GEMINI_API_KEY:
            raise ValueError("Gemini API key is not configured")
            
        # Use Gemini with medical context prompt wrapping
        model = genai.GenerativeModel('gemini-1.5-pro')  # Using a more capable model for medical queries
        
        # Wrap the prompt with medical context
        medical_prompt = f"""As a medical AI assistant, answer the following medical question with factual information. 
                         Be thorough and evidence-based, but accessible in your explanation: {prompt}"""
        
        response = await model.generate_content_async(medical_prompt)
        
        if not response.text:
            return ["I'm sorry,", " I", " couldn't", " generate", " a", " medical", " response.", " Please", " consult", " a", " healthcare", " professional."]
        
        # Split response into tokens for streaming simulation
        words = response.text.split()
        tokens = []
        for word in words:
            tokens.append(word)
            tokens.append(" ")
        return tokens
        
    except (GoogleAPIError, ValueError) as e:
        # Fallback response if API fails
        return ["I'm", " sorry,", " I'm", " having", " trouble", " accessing", " medical", " information.", " Please", " consult", " a", " healthcare", " professional."]

async def stream_tokens(tokens):
    for tok in tokens:
        yield f"data: {tok}\n\n"
        await asyncio.sleep(0.1)  # Slightly faster token stream

@app.post("/stream")
async def stream_response(request: Request):
    try:
        body = await request.json()
        message = body.get("message", "")
        if not message:
            raise HTTPException(status_code=400, detail="Message is required")
            
        intent = classify_intent(message)
        tokens = await query_medgemma(message) if intent == "medical" else await query_gemini_flash(message)
        return StreamingResponse(stream_tokens(tokens), media_type="text/event-stream")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/tts")
async def elevenlabs_tts(request: Request):
    try:
        body = await request.json()
        text = body.get("text", "")
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
            
        if not ELEVENLABS_API_KEY:
            raise HTTPException(status_code=500, detail="TTS API key is not configured")
            
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "voice_settings": { "stability": 0.5, "similarity_boost": 0.75 }
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True)
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"TTS API error: {response.text}")
            
        return StreamingResponse(response.iter_content(chunk_size=1024), media_type="audio/mpeg")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error connecting to TTS service: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "services": {
        "elevenlabs": "available" if ELEVENLABS_API_KEY else "unavailable",
        "deepgram": "available" if DEEPGRAM_API_KEY else "unavailable",
        "gemini": "available" if GEMINI_API_KEY else "unavailable"
    }}

@app.post("/deepgram-proxy")
async def deepgram_proxy(request: Request):
    """Proxy endpoint for Deepgram to avoid exposing API keys in frontend"""
    try:
        # Make sure we have the API key
        if not DEEPGRAM_API_KEY:
            raise HTTPException(status_code=500, detail="Deepgram API key not configured")
            
        # Get the audio data from the request
        form_data = await request.form()
        audio = form_data.get('audio')
        if not audio:
            raise HTTPException(status_code=400, detail="Audio data required")
        
        audio_content = await audio.read()
        
        # Forward to Deepgram
        url = "https://api.deepgram.com/v1/listen"
        headers = {
            "Authorization": f"Token {DEEPGRAM_API_KEY}",
            "Content-Type": "audio/wav"
        }
        
        # Configure Deepgram parameters
        params = {
            "model": "nova-2",  # Use their latest model
            "smart_format": "true",
            "diarize": "false",
            "punctuate": "true"
        }
        
        # Send the request to Deepgram
        response = requests.post(
            url, 
            headers=headers, 
            params=params,
            data=audio_content
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Deepgram API error: {response.text}"
            )
            
        return response.json()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT proxy error: {str(e)}")

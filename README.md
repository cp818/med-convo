# Full Conversational AI System

This project is a real-time voice-based conversational AI assistant combining:
- 🎙️ Deepgram (STT)
- 🧠 Gemini Flash / MedGemma (LLM Routing)
- 🔊 ElevenLabs (TTS)
- 📡 LiveKit (Audio streaming)
- 🚀 Can be deployed on GCP (Cloud Run + Secret Manager) or Vercel

---

## 📁 Project Structure

- `backend/` - FastAPI app for LLM logic, TTS, STT routing
- `frontend/` - HTML + JS user interface for voice interactions
- `token_server/` - FastAPI service that issues LiveKit access tokens

---

## 🚀 Deployment

### 1. Prerequisites
- Python 3.10+
- Docker + GCP SDK
- LiveKit Cloud account
- Deepgram API Key
- ElevenLabs API Key

### 2. GCP Deployment

#### Deploy Backend

```bash
cd backend
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/convo-backend
gcloud run deploy convo-backend \
  --image gcr.io/YOUR_PROJECT_ID/convo-backend \
  --region us-central1 \
  --allow-unauthenticated \
  --update-secrets ELEVENLABS_API_KEY=ELEVENLABS_API_KEY:latest,DEEPGRAM_API_KEY=DEEPGRAM_API_KEY:latest
```

#### Deploy Token Server

```bash
cd token_server
chmod +x deploy.sh
./deploy.sh
```

#### Deploy Frontend (optional Firebase Hosting or GCS)

```bash
gsutil mb -p YOUR_PROJECT_ID -l us-central1 gs://your-bucket-name
gsutil cp -r frontend/* gs://your-bucket-name
```

Or use Firebase:
```bash
firebase init
firebase deploy
```

### 3. GitHub and Vercel Deployment

#### Push to GitHub

```bash
# Initialize Git repository
git init

# Add all files
git add .

# Commit changes
git commit -m "Initial commit"

# Add remote GitHub repository
git remote add origin https://github.com/cp818/med-convo.git

# Push to GitHub
git push -u origin main
```

#### Deploy on Vercel

1. Connect your GitHub repository to Vercel
2. Configure the following environment variables in the Vercel project settings:
   - `ELEVENLABS_API_KEY`
   - `DEEPGRAM_API_KEY`
   - `GEMINI_API_KEY`
   - `LIVEKIT_API_KEY`
   - `LIVEKIT_SECRET`
3. Deploy the project

The `vercel.json` file in the repository will handle the configuration of build settings and API routes.

---

## 🔐 Secrets Setup

```bash
gcloud secrets create ELEVENLABS_API_KEY --data-file=<(echo "your-key")
gcloud secrets create DEEPGRAM_API_KEY --data-file=<(echo "your-key")
gcloud secrets create LIVEKIT_API_KEY --data-file=<(echo "your-key")
gcloud secrets create LIVEKIT_SECRET --data-file=<(echo "your-secret")
```

---

## ✅ Usage

1. Open frontend in browser
2. Click "Start Talking" to send audio to Deepgram
3. Transcription is routed to Gemini or MedGemma
4. Response is spoken via ElevenLabs TTS
5. Audio streamed in real-time over LiveKit

---

Built with ❤️ by Knowlithic AI

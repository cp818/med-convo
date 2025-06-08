let mediaRecorder;
let audioChunks = [];
let livekitRoom;
let livekitToken;
let audioTrack;

// Configuration - edit these URLs based on your deployment
const BACKEND_URL = window.location.hostname === 'localhost' ? 'http://localhost:8080' : '/api';
const TOKEN_SERVER_URL = window.location.hostname === 'localhost' ? 'http://localhost:8081' : '/api';
const DEEPGRAM_PROXY_URL = `${BACKEND_URL}/deepgram-proxy`;

async function initLiveKit() {
  try {
    // Generate a random user ID
    const userId = 'user-' + Math.floor(Math.random() * 100000);
    const roomName = 'voiceroom';
    
    // Get token from token server
    const response = await fetch(`${TOKEN_SERVER_URL}/get-token?identity=${userId}&room=${roomName}`);
    if (!response.ok) throw new Error('Failed to get LiveKit token');
    
    const data = await response.json();
    livekitToken = data.token;
    
    // Connect to LiveKit if the SDK is available
    if (window.LivekitClient) {
      livekitRoom = new window.LivekitClient.Room();
      await livekitRoom.connect(`wss://your-livekit-host.livekit.cloud`, livekitToken);
      console.log('Connected to LiveKit room:', roomName);
    } else {
      console.warn('LiveKit client not loaded');
    }
  } catch (error) {
    console.error('LiveKit initialization error:', error);
    appendMessage("⚠️ LiveKit connection failed");
  }
}

async function startMic() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();

    appendMessage("🎙️ Listening...");
    
    mediaRecorder.ondataavailable = event => {
      audioChunks.push(event.data);
    };

    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
      audioChunks = [];
      sendAudioToSTT(audioBlob);
    };

    // If LiveKit is initialized, publish the audio track
    if (livekitRoom?.state === 'connected') {
      audioTrack = await window.LivekitClient.LocalAudioTrack.createFromMediaStreamTrack(stream.getAudioTracks()[0]);
      await livekitRoom.localParticipant.publishTrack(audioTrack);
    }

    setTimeout(() => {
      stopMic();
    }, 8000); // 8 seconds max sample
  } catch (error) {
    console.error('Microphone access error:', error);
    appendMessage("⚠️ Could not access microphone");
  }
}

function stopMic() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    appendMessage("✅ Processing audio...");
  }
  
  // Unpublish LiveKit track if it exists
  if (audioTrack && livekitRoom?.state === 'connected') {
    livekitRoom.localParticipant.unpublishTrack(audioTrack);
    audioTrack = null;
  }
}

function sendAudioToSTT(blob) {
  const formData = new FormData();
  formData.append("audio", blob);

  // Use the backend as a proxy to Deepgram rather than calling directly with API key
  fetch(`${BACKEND_URL}/deepgram-proxy`, {
    method: "POST",
    body: formData
  })
  .then(res => {
    if (!res.ok) throw new Error('Deepgram API error: ' + res.status);
    return res.json();
  })
  .then(data => {
    if (data.results && data.results.channels && data.results.channels[0]) {
      const transcript = data.results.channels[0].alternatives[0].transcript;
      if (transcript.trim()) {
        appendMessage("🗣️ You: " + transcript);
        getAIResponse(transcript);
      } else {
        appendMessage("⚠️ No speech detected");
      }
    } else {
      throw new Error('Invalid response format from STT service');
    }
  })
  .catch(error => {
    console.error('Speech-to-text error:', error);
    appendMessage("⚠️ Speech recognition failed");
  });
}

function getAIResponse(text) {
  // Display thinking indicator
  const thinkingId = 'thinking-' + Date.now();
  appendMessage(`<div id="${thinkingId}">🤖 AI is thinking...</div>`);
  
  fetch(`${BACKEND_URL}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text })
  })
  .then(res => {
    if (!res.ok) throw new Error('AI Response error: ' + res.status);
    
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let aiReply = '';
    
    // Remove thinking indicator once we start getting a response
    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) thinkingEl.remove();
    
    reader.read().then(function process({ done, value }) {
      if (done) {
        appendMessage("🤖 AI: " + aiReply);
        playTTS(aiReply);
        return;
      }
      let chunk = decoder.decode(value, { stream: true });
      aiReply += chunk.replace(/data: /g, "").replace(/\n\n/g, "");
      reader.read().then(process);
    });
  })
  .catch(error => {
    console.error('AI response error:', error);
    // Remove thinking indicator if there was an error
    const thinkingEl = document.getElementById(thinkingId);
    if (thinkingEl) thinkingEl.remove();
    
    appendMessage("⚠️ Error getting AI response");
  });
}

function playTTS(text) {
  appendMessage("🔊 Playing audio response...");
  
  fetch(`${BACKEND_URL}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  }).then(response => {
    if (!response.ok) throw new Error('TTS error: ' + response.status);
    
    const audio = new Audio();
    const reader = response.body.getReader();
    const stream = new ReadableStream({
      start(controller) {
        function push() {
          reader.read().then(({ done, value }) => {
            if (done) {
              controller.close();
              return;
            }
            controller.enqueue(value);
            push();
          });
        }
        push();
      }
    });

    const audioBlob = new Response(stream).blob().then(blob => {
      const url = URL.createObjectURL(blob);
      audio.src = url;
      
      // If LiveKit is connected, stream the audio through it
      if (livekitRoom?.state === 'connected') {
        try {
          const audioElement = audio;
          audioElement.oncanplaythrough = async () => {
            const ctx = new AudioContext();
            const source = ctx.createMediaElementSource(audioElement);
            const destination = ctx.createMediaStreamDestination();
            source.connect(destination);
            source.connect(ctx.destination); // Also play locally
            
            // Get MediaStreamTrack from destination stream
            const track = destination.stream.getAudioTracks()[0];
            if (track) {
              const livekitTrack = await window.LivekitClient.LocalAudioTrack.createFromMediaStreamTrack(track);
              await livekitRoom.localParticipant.publishTrack(livekitTrack);
              
              audioElement.onended = () => {
                livekitRoom.localParticipant.unpublishTrack(livekitTrack);
              };
            }
          };
        } catch (e) {
          console.error('Error streaming TTS through LiveKit:', e);
        }
      }
      
      audio.play().catch(e => console.error('Audio playback error:', e));
    });
  })
  .catch(error => {
    console.error('TTS error:', error);
    appendMessage("⚠️ Error playing audio response");
  });
}

function appendMessage(message) {
  const msgDiv = document.getElementById("messages");
  msgDiv.innerHTML += `<div>${message}</div>`;
  msgDiv.scrollTop = msgDiv.scrollHeight;
}

// Initialize LiveKit when page loads
document.addEventListener('DOMContentLoaded', async () => {
  try {
    // Check if backend services are healthy
    const healthResponse = await fetch(`${BACKEND_URL}/health`);
    if (healthResponse.ok) {
      const healthData = await healthResponse.json();
      console.log('Backend services status:', healthData);
      
      if (!healthData.services.elevenlabs) {
        appendMessage("⚠️ TTS service unavailable");
      }
      
      if (!healthData.services.gemini) {
        appendMessage("⚠️ AI service unavailable");
      }
    }
    
    // Initialize LiveKit
    await initLiveKit();
    appendMessage("✅ System ready. Click 'Start Talking' to begin.");
  } catch (error) {
    console.error('Initialization error:', error);
    appendMessage("⚠️ Some services may be unavailable");
  }
});

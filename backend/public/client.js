// Connect to Deepgram via WebSocket (placeholder)
let socket = new WebSocket("wss://api.deepgram.com/v1/listen?model=nova");
socket.onopen = () => {
  console.log("Connected to Deepgram.");
};
socket.onmessage = (msg) => {
  let data = JSON.parse(msg.data);
  let transcript = data.channel?.alternatives[0]?.transcript;
  if (transcript && data.is_final) {
    console.log("Transcript:", transcript);
    fetch('/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: transcript })
    }).then(res => {
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      reader.read().then(function process({ done, value }) {
        if (done) return;
        let chunk = decoder.decode(value, { stream: true });
        console.log("AI:", chunk);
        reader.read().then(process);
      });
    });
  }
};


// === ElevenLabs TTS Streaming ===
// ElevenLabs TTS audio playback (streamed)
function playTTS(text) {
  fetch('/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  }).then(response => {
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
      audio.play();
    });
  });
}


// === LiveKit Client Integration ===
// LiveKit client-side connection
import { connect } from 'livekit-client';

let room;
async function startLiveKitSession(token, url) {
  room = await connect(url, token, {
    autoSubscribe: true
  });

  room.on('trackSubscribed', (track, publication, participant) => {
    if (track.kind === 'audio') {
      track.attach().play();
    }
  });

  const micTrack = await LiveKitLocalTrack.createAudioTrack();
  room.localParticipant.publishTrack(micTrack);
}

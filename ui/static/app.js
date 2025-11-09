const els = {
  micBtn: document.getElementById("mic-btn"),
  micLabel: document.getElementById("mic-label"),
  status: document.getElementById("status-text"),
  transcript: document.getElementById("transcript-text"),
  reply: document.getElementById("reply-text"),
  apiDisplay: document.getElementById("api-base-display"),
  apiEditBtn: document.getElementById("api-edit-btn"),
  toastTemplate: document.getElementById("toast-template"),
};

const storedBase = (localStorage.getItem("voice-agent-api") || "").trim();
let API_BASE =
  storedBase ||
  (window.location ? window.location.origin.replace(/\/$/, "") : "http://127.0.0.1:8010");
if (!API_BASE) {
  API_BASE = "http://127.0.0.1:8010";
}
els.apiDisplay.textContent = API_BASE;

const state = {
  stream: null,
  recorder: null,
  chunks: [],
  isRecording: false,
  isProcessing: false,
  isSpeaking: false,
  audioCtx: null,
  speakingAudio: null,
};

els.apiEditBtn.addEventListener("click", () => {
  const value = prompt("Backend base URL", API_BASE) || "";
  const clean = value.trim().replace(/\/$/, "");
  if (!clean) return;
  API_BASE = clean;
  els.apiDisplay.textContent = API_BASE;
  localStorage.setItem("voice-agent-api", API_BASE);
  toast(`API base set to ${API_BASE}`);
});

function toast(message, isError = false) {
  const tpl = els.toastTemplate.content.firstElementChild.cloneNode(true);
  tpl.textContent = message;
  tpl.style.borderColor = isError ? "rgba(251, 113, 133, 0.5)" : "rgba(56, 189, 248, 0.4)";
  document.body.appendChild(tpl);
  setTimeout(() => tpl.remove(), 3500);
}

function setStatus(text) {
  els.status.textContent = text;
}

function setTranscript(text) {
  els.transcript.textContent = text || "(silence)";
}

function setReply(text) {
  els.reply.textContent = text || "(no reply)";
}

function setMicMode(mode) {
  els.micBtn.classList.remove("listening", "thinking", "speaking");
  els.micBtn.classList.add(mode);
  const labels = {
    listening: "Listening… tap to stop",
    thinking: "Thinking…",
    speaking: "Speaking…",
    idle: "Tap to talk",
  };
  els.micLabel.textContent = labels[mode] || labels.idle;
}

function ensureAudioContext() {
  if (!state.audioCtx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    state.audioCtx = new Ctx();
  }
  return state.audioCtx;
}

async function toggleRecording() {
  if (state.isSpeaking) {
    stopSpeaking();
    return;
  }
  if (state.isProcessing) {
    toast("Hold on, I’m still responding.");
    return;
  }
  if (state.isRecording) {
    stopRecording();
  } else {
    await startRecording();
  }
}

async function startRecording() {
  if (!navigator.mediaDevices?.getUserMedia) {
    toast("This browser can’t access the microphone.", true);
    return;
  }
  try {
    if (!state.stream) {
      state.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    const mimeType = pickMimeType();
    state.recorder = new MediaRecorder(state.stream, mimeType ? { mimeType } : undefined);
    state.chunks = [];
    state.recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        state.chunks.push(event.data);
      }
    };
    state.recorder.onstop = () => {
      finalizeRecording().catch((err) => {
        console.error(err);
        toast(err.message || "Recording failed.", true);
        resetMic();
      });
    };
    state.recorder.start();
    state.isRecording = true;
    setMicMode("listening");
    setStatus("Listening… tap to stop.");
  } catch (err) {
    console.error(err);
    toast("Unable to access the microphone.", true);
  }
}

function stopRecording() {
  if (!state.isRecording || !state.recorder) return;
  state.isRecording = false;
  try {
    state.recorder.stop();
    setMicMode("thinking");
    setStatus("Give me a second to process that.");
  } catch (err) {
    console.error(err);
    resetMic();
  }
}

async function finalizeRecording() {
  if (!state.chunks.length) {
    resetMic();
    return;
  }
  const mimeType = state.recorder?.mimeType || "audio/webm";
  const blob = new Blob(state.chunks.slice(), { type: mimeType });
  state.recorder = null;
  state.chunks = [];
  state.isProcessing = true;
  let finalStatus = "Idle";

  try {
    const wavBlob = await convertBlobToWav(blob);
    const outcome = await runPipeline(wavBlob);
    if (outcome === "silent") {
      finalStatus = "Didn’t hear anything — tap to talk again.";
    } else if (state.isSpeaking) {
      finalStatus = null;
    }
  } catch (err) {
    console.error(err);
    toast(err.message || "Something went wrong.", true);
    finalStatus = "Something went wrong — tap to talk again.";
  } finally {
    state.isProcessing = false;
    if (finalStatus) {
      resetMic(finalStatus);
    }
  }
}

function resetMic(message) {
  state.isRecording = false;
  setMicMode("idle");
  setStatus(message || "Idle");
}

function pickMimeType() {
  if (!window.MediaRecorder || !MediaRecorder.isTypeSupported) return null;
  const candidates = ["audio/webm;codecs=pcm", "audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || null;
}

async function convertBlobToWav(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const ctx = ensureAudioContext();
  const audioBuffer = await new Promise((resolve, reject) =>
    ctx.decodeAudioData(arrayBuffer.slice(0), resolve, reject)
  );
  const samples = mixToMono(audioBuffer);
  const wavBuffer = encodeWav(samples, audioBuffer.sampleRate);
  return new Blob([wavBuffer], { type: "audio/wav" });
}

function mixToMono(buffer) {
  const { numberOfChannels, length } = buffer;
  if (numberOfChannels === 1) return buffer.getChannelData(0);
  const result = new Float32Array(length);
  for (let channel = 0; channel < numberOfChannels; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let i = 0; i < length; i += 1) {
      result[i] += data[i];
    }
  }
  for (let i = 0; i < length; i += 1) {
    result[i] /= numberOfChannels;
  }
  return result;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  let offset = 0;

  const writeString = (str) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
    offset += str.length;
  };

  writeString("RIFF");
  view.setUint32(offset, 36 + samples.length * 2, true);
  offset += 4;
  writeString("WAVEfmt ");
  view.setUint32(offset, 16, true);
  offset += 4;
  view.setUint16(offset, 1, true);
  offset += 2;
  view.setUint16(offset, 1, true);
  offset += 2;
  view.setUint32(offset, sampleRate, true);
  offset += 4;
  view.setUint32(offset, sampleRate * 2, true);
  offset += 4;
  view.setUint16(offset, 2, true);
  offset += 2;
  view.setUint16(offset, 16, true);
  offset += 2;
  writeString("data");
  view.setUint32(offset, samples.length * 2, true);
  offset += 4;

  for (let i = 0; i < samples.length; i += 1, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return buffer;
}

async function runPipeline(wavBlob) {
  setStatus("Transcribing what you said…");
  const asrData = await callAsr(wavBlob);
  const transcript = (asrData.transcript || "").trim();
  const heardSomething = Boolean(transcript);
  setTranscript(transcript || "(silence)");
  if (!heardSomething) {
    toast("I didn’t hear anything. Let’s try again.");
    setMicMode("idle");
    return "silent";
  }

  setMicMode("thinking");
  setStatus("Thinking…");
  const agentData = await callAgent(transcript);
  const replyText = (agentData.text || "").trim();
  setReply(replyText || "I’m not sure what to say.");

  setMicMode("speaking");
  setStatus("Speaking…");
  await speakReply(replyText || "I’m not sure what to say.");
  return "ok";
}

async function speakReply(text) {
  try {
    const replyBlob = await callTts(text);
    const url = URL.createObjectURL(replyBlob);
    if (state.speakingAudio) {
      state.speakingAudio.pause();
    }
    const audio = new Audio(url);
    state.speakingAudio = audio;
    state.isSpeaking = true;
    setMicMode("speaking");
    setStatus("Speaking… tap to stop.");
    audio.addEventListener("ended", () => stopSpeaking(false));
    try {
      await audio.play();
    } catch (err) {
      console.warn("Autoplay blocked:", err);
      toast("Reply ready — tap anywhere to allow audio.", true);
      stopSpeaking(false);
    }
  } catch (err) {
    console.error(err);
    toast("Couldn’t play the reply audio.", true);
    stopSpeaking(false);
  }
}

function stopSpeaking(manual = true) {
  if (state.speakingAudio) {
    state.speakingAudio.pause();
    state.speakingAudio.currentTime = 0;
    state.speakingAudio = null;
  }
  if (!state.isSpeaking && manual) {
    resetMic();
    return;
  }
  state.isSpeaking = false;
  if (manual) {
    resetMic("Stopped the reply — tap to talk.");
  } else {
    resetMic();
  }
}

async function callAsr(wavBlob) {
  const form = new FormData();
  const file = new File([wavBlob], "audio.wav", { type: "audio/wav" });
  form.append("file", file);
  return fetchJson("/asr", { method: "POST", body: form });
}

async function callAgent(transcript) {
  return fetchJson("/agent", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript }),
  });
}

async function callTts(text) {
  const resp = await fetch(`${API_BASE}/tts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!resp.ok) {
    throw new Error(`TTS failed (${resp.status})`);
  }
  const buffer = await resp.arrayBuffer();
  return new Blob([buffer], { type: "audio/wav" });
}

async function fetchJson(path, options) {
  const resp = await fetch(`${API_BASE}${path}`, options);
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`HTTP ${resp.status}: ${detail || "request failed"}`);
  }
  return resp.json();
}

function wireMic() {
  if (!window.MediaRecorder) {
    toast("MediaRecorder API is not supported here.", true);
    els.micBtn.disabled = true;
    setStatus("Unsupported browser");
    return;
  }
  els.micBtn.addEventListener("click", () => toggleRecording());
}

wireMic();
setStatus("Idle");

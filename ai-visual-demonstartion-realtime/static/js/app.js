const video = document.getElementById('webcam');
const stopBtn = document.getElementById('stopBtn');
const languageSelect = document.getElementById('languageSelect');
const baseCaption = document.getElementById('baseCaption');
const translatedCaption = document.getElementById('translatedCaption');

let captureInterval = null;
let isProcessing = false;

// Start webcam
async function startWebcam() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
  } catch (err) {
    alert('Webcam error: ' + err.message);
  }
}

// Start frame capture
function startCapturing(intervalMs = 2500) {
  captureInterval = setInterval(captureFrame, intervalMs);
}

// Stop frame capture
function stopCapturing() {
  clearInterval(captureInterval);
  baseCaption.innerText = 'Stopped.';
  translatedCaption.innerText = '–';
}

// Frame capture + caption
function captureFrame() {
  if (isProcessing) return;
  isProcessing = true;

  const canvas = document.createElement('canvas');
  canvas.width = 320;
  canvas.height = 240;
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob(async (blob) => {
    const formData = new FormData();
    formData.append('frame', blob, 'frame.jpg');
    formData.append('lang', languageSelect.value);

    try {
      const response = await fetch('/describe-frame', {
        method: 'POST',
        body: formData
      });
      const result = await response.json();

      const caption = result.description || 'No description.';
      baseCaption.innerText = caption;

      // Check if translation is available
      if (result.translated_description && languageSelect.value !== 'en') {
        translatedCaption.innerText = result.translated_description;
      } else {
        translatedCaption.innerText = '–'; // Hide translated caption if not available
      }

      // Speak the caption (voiceover)
      speak(caption);

    } catch (err) {
      baseCaption.innerText = 'Error';
      translatedCaption.innerText = err.message;
    } finally {
      isProcessing = false;
    }
  }, 'image/jpeg');
}

// Function to speak the caption aloud using the SpeechSynthesis API
function speak(text) {
  const lang = languageSelect.value || 'en'; // Get selected language for voice
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = lang;
  utterance.rate = 1;

  speechSynthesis.cancel(); // stop any ongoing speech
  speechSynthesis.speak(utterance);
}

// Init on load
window.addEventListener('DOMContentLoaded', () => {
  startWebcam();
  startCapturing(); // auto start capturing
  stopBtn.addEventListener('click', stopCapturing);
});

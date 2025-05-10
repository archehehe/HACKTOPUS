# app.py
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pyttsx3
import os
import json
import logging
from gtts import gTTS
import re
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import platform

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# Setup logging
logging.basicConfig(filename='speak4mepro.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class Speak4MeProBackend:
    def __init__(self):
        self.engine = None
        self.voices = []
        self.current_voice = 0
        self.rate = 150
        self.volume = 1.0
        self.pitch = 0
        self.use_gtts = False
        self.pronunciation_dict = self.load_data('custom_pronunciations.json', {})
        self.speech_history = self.load_data('speech_history.json', [])
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        self.initialize_engine()

    def load_data(self, filename, default):
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load {filename}: {e}")
        return default

    def save_data(self, filename, data):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logging.info(f"Saved {filename}")
        except Exception as e:
            logging.error(f"Failed to save {filename}: {e}")

    def initialize_engine(self):
        system = platform.system()
        logging.info(f"Initializing engine on {system}")
        for attempt in range(3):
            try:
                self.engine = pyttsx3.init('sapi5' if system == "Windows" else None)
                self.voices = self.engine.getProperty('voices') or []
                if self.voices:
                    for i, voice in enumerate(self.voices):
                        if 'female' in voice.name.lower() or 'zira' in voice.name.lower():
                            self.current_voice = i
                            break
                    logging.info(f"Initialized with SAPI5 voices: {[v.name for v in self.voices]}")
                    return
                else:
                    logging.warning("No SAPI5 voices found, attempting gTTS fallback")
            except Exception as e:
                logging.error(f"SAPI5 init attempt {attempt+1} failed: {e}")
            
            self.use_gtts = True
            self.engine = None
            logging.info("Switching to gTTS fallback")
            return

    def apply_pronunciations(self, text):
        if not text or not self.pronunciation_dict:
            return text
        for word, pron in self.pronunciation_dict.items():
            if not word or not pron:
                continue
            pattern = r'\b' + re.escape(word) + r'\b'
            text = re.sub(pattern, pron, text, flags=re.IGNORECASE)
        return text

    def update_engine_settings(self):
        if self.voices and not self.use_gtts:
            try:
                self.engine.setProperty('voice', self.voices[self.current_voice].id)
                self.engine.setProperty('rate', self.rate)
                self.engine.setProperty('volume', self.volume)
                if self.pitch != 0:
                    try:
                        self.engine.setProperty('pitch', self.pitch)
                    except:
                        pass
            except Exception as e:
                logging.error(f"Failed to set SAPI5 properties: {e}")
                self.use_gtts = True
                self.engine = None

backend = Speak4MeProBackend()

@app.route('/api/voices', methods=['GET'])
def get_voices():
    if backend.use_gtts:
        return jsonify(['gTTS'])
    return jsonify([v.name for v in backend.voices])

@app.route('/api/speak', methods=['POST'])
def speak():
    data = request.json
    text = backend.apply_pronunciations(data.get('text', ''))
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    backend.rate = data.get('rate', 150)
    backend.volume = data.get('volume', 1.0)
    backend.pitch = data.get('pitch', 0)
    voice_index = data.get('voice_index', 0)
    if voice_index < len(backend.voices):
        backend.current_voice = voice_index
    
    backend.update_engine_settings()
    filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    
    if backend.use_gtts:
        try:
            tts = gTTS(text=text, lang='en')
            tts.save(filename)
        except Exception as e:
            logging.error(f"gTTS error: {e}")
            return jsonify({'error': str(e)}), 500
    else:
        backend.engine.save_to_file(text, filename)
        backend.engine.runAndWait()
    
    backend.speech_history.append({'text': text, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
    backend.save_data('speech_history.json', backend.speech_history)
    return send_file(filename, mimetype='audio/mpeg', as_attachment=True)

@app.route('/api/record', methods=['POST'])
def record():
    data = request.json
    text = backend.apply_pronunciations(data.get('text', ''))
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    try:
        tts = gTTS(text=text, lang='en')
        tts.save(filename)
        return jsonify({'filename': filename})
    except Exception as e:
        logging.error(f"Recording error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/record/<filename>', methods=['GET'])
def get_recording(filename):
    return send_file(filename, mimetype='audio/mpeg', as_attachment=True)

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(backend.speech_history)

@app.route('/api/clear_history', methods=['POST'])
def clear_history():
    backend.speech_history = []
    backend.save_data('speech_history.json', backend.speech_history)
    return jsonify({'message': 'History cleared'})

@app.route('/api/sentiment', methods=['POST'])
def analyze_sentiment():
    data = request.json
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    scores = backend.sentiment_analyzer.polarity_scores(text)
    compound = scores['compound']
    if compound >= 0.05:
        sentiment = "Positive"
        suggested_emotion = "Happy"
    elif compound <= -0.05:
        sentiment = "Negative"
        suggested_emotion = "Sad"
    else:
        sentiment = "Neutral"
        suggested_emotion = "Normal"
    return jsonify({'sentiment': sentiment, 'suggested_emotion': suggested_emotion})

@app.route('/api/pronunciation', methods=['POST'])
def add_pronunciation():
    data = request.json
    word = data.get('word', '')
    pron = data.get('pron', '')
    if not word or not pron:
        return jsonify({'error': 'Invalid word or pronunciation'}), 400
    backend.pronunciation_dict[word.lower()] = pron
    backend.save_data('custom_pronunciations.json', backend.pronunciation_dict)
    return jsonify({'message': f"Added: {word} -> {pron}"})

@app.route('/api/clear_pronunciations', methods=['POST'])
def clear_pronunciations():
    backend.pronunciation_dict = {}
    backend.save_data('custom_pronunciations.json', backend.pronunciation_dict)
    return jsonify({'message': 'Pronunciation dictionary cleared'})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
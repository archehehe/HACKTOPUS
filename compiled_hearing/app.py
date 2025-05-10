from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
import subprocess
import os
import json
import platform
import urllib.request
import zipfile
from vosk import Model, KaldiRecognizer
import speech_recognition as sr
from datetime import datetime


app = Flask(__name__)
app.secret_key = 'your-secret-key-here' 
languages = {
    'en': ('English', 'en-US'),
    'hi': ('Hindi', 'hi-IN'),
    'es': ('Spanish', 'es-ES'),
    'fr': ('French', 'fr-FR'),
    'de': ('German', 'de-DE')
}


UPLOAD_FOLDER = 'uploads'
AUDIO_FOLDER = 'audio_extracts'
CAPTION_FOLDER = 'captions'
MODEL_FOLDER = 'model'
ALLOWED_EXTENSIONS = {'mp4', 'mov', 'avi', 'mkv'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['AUDIO_FOLDER'] = AUDIO_FOLDER
app.config['CAPTION_FOLDER'] = CAPTION_FOLDER
app.config['MODEL_FOLDER'] = MODEL_FOLDER
# Emergency services configuration (example)
app.config['EMERGENCY_SERVICES'] = {
    'police': '911',
    'fire': '911',
    'medical': '911',
    'custom': '112'  # EU emergency number
}


os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(CAPTION_FOLDER, exist_ok=True)
os.makedirs(MODEL_FOLDER, exist_ok=True)



def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_ffmpeg_path():
    """Find FFmpeg executable with multiple fallback options"""
    if platform.system() == 'Windows':
        paths_to_try = [
            'ffmpeg',
            r'C:\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
            r'C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe'
        ]
    else:
        paths_to_try = [
            'ffmpeg',
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg'
        ]
    
    for path in paths_to_try:
        try:
            subprocess.run([path, '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return path
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    return None

FFMPEG_PATH = get_ffmpeg_path()

def extract_audio(video_path):
    """Extract audio from video using ffmpeg"""
    if not FFMPEG_PATH:
        raise RuntimeError("FFmpeg not found. Please install FFmpeg.")
    
    audio_filename = os.path.splitext(os.path.basename(video_path))[0] + '.wav'
    audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_filename)
    
    command = [FFMPEG_PATH, '-i', video_path, '-ac', '1', '-ar', '16000', '-vn', '-y', audio_path]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"Error extracting audio: {e.stderr.decode('utf-8')}")
        return None

def transcribe_audio(audio_path):
    """Transcribe audio using Vosk"""
    try:
        if not os.path.exists(audio_path):
            print(f"Audio file not found: {audio_path}")
            return None
        
        model_name = "vosk-model-en-us-0.22"
        model_url = f"https://alphacephei.com/vosk/models/{model_name}.zip"
        model_path = os.path.join(app.config['MODEL_FOLDER'], model_name)
        
        if not os.path.exists(model_path):
            print("Downloading Vosk model...")
            os.makedirs(app.config['MODEL_FOLDER'], exist_ok=True)
            model_zip = os.path.join(app.config['MODEL_FOLDER'], f"{model_name}.zip")
            urllib.request.urlretrieve(model_url, model_zip)
            
            with zipfile.ZipFile(model_zip, 'r') as zip_ref:
                zip_ref.extractall(app.config['MODEL_FOLDER'])
            os.remove(model_zip)

        model = Model(model_path)
        recognizer = KaldiRecognizer(model, 16000)

        transcript_parts = []
        chunk_size = 4000
        
        with open(audio_path, 'rb') as audio_file:
            while True:
                data = audio_file.read(chunk_size)
                if len(data) == 0:
                    break
                
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    if 'text' in result:
                        transcript_parts.append(result['text'])
            
            final_result = json.loads(recognizer.FinalResult())
            if 'text' in final_result:
                transcript_parts.append(final_result['text'])
        
        full_transcript = ' '.join(filter(None, transcript_parts))
        full_transcript = ' '.join(full_transcript.split())
        
        if not full_transcript:
            return None
        
        if full_transcript[-1] not in {'.', '!', '?'}:
            full_transcript += '.'
        
        return full_transcript
    
    except Exception as e:
        print(f"Transcription failed: {str(e)}")
        return None

def create_srt_file(transcript, base_filename):
    """Create SRT file"""
    srt_path = os.path.join(app.config['CAPTION_FOLDER'], f"{base_filename}.srt")
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write("1\n00:00:00,000 --> 00:10:00,000\n")
        f.write(f"{transcript}\n")
    return srt_path



class SpeechToTextConverter:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 400
        self.recognizer.dynamic_energy_threshold = True
        self.Languages = {
            '1': ('English', 'en-US'),
            '2': ('Spanish', 'es-ES'),
            '3': ('French', 'fr-FR'),
            '4': ('German', 'de-DE'),
            '5': ('Japanese', 'ja-JP')
        }

    def get_audio_input(self, source):
        print("\nSpeak now (waiting for input)...")
        try:
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
            return audio
        except sr.WaitTimeoutError:
            print("No speech detected. Please try again.")
            return None

    def transcribe_audio(self, audio, language_code):
    
        try:
            text = self.recognizer.recognize_google(audio, language=language_code)
            return text
        except sr.UnknownValueError:
            print("Speech recognition could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results from Google Speech Recognition service; {e}")
        return None



    def save_results(self, text, audio=None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        txt_file = f"mic_transcription_{timestamp}.txt"
        with open(os.path.join(app.config['CAPTION_FOLDER'], txt_file), 'w') as f:
            f.write(text)
        if audio:
            wav_file = f"mic_audio_{timestamp}.wav"
            with open(os.path.join(app.config['AUDIO_FOLDER'], wav_file), 'wb') as f:
                f.write(audio.get_wav_data())
        return txt_file

    def select_language(self):
        print("\nAvailable languages:")
        for key, (name, _) in self.languages.items():
            print(f"{key}. {name}")
        while True:
            choice = input("Select language (1-5): ").strip()
            if choice in self.languages:
                return self.languages[choice][1]
            print("Invalid choice. Please try again.")


@app.route('/', methods=['GET', 'POST'])
def index():
    if not FFMPEG_PATH:
        flash("FFmpeg not found! Video processing will not work.", "error")

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No selected file', 'error')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            try:
                
                file.save(video_path)

                
                audio_path = extract_audio(video_path)
                if not audio_path:
                    flash('Failed to extract audio from video', 'error')
                    return redirect(request.url)

               
                transcript = transcribe_audio(audio_path)
                if not transcript:
                    flash('Failed to transcribe audio', 'error')
                    return redirect(request.url)

                
                base_filename = os.path.splitext(filename)[0]
                create_srt_file(transcript, base_filename)

                
                txt_path = os.path.join(app.config['CAPTION_FOLDER'], f"{base_filename}.txt")
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(transcript)

                flash('Transcription completed successfully!', 'success')

                return render_template('results.html', video_file=filename, transcript=transcript, base_filename=base_filename)

            except Exception as e:
                flash(f'Error during processing: {str(e)}', 'error')
                return redirect(request.url)
        else:
            flash('Invalid file format. Please upload a video file.', 'error')
            return redirect(request.url)

   
    return render_template('upload.html', languages=languages)

@app.route('/emergency', methods=['GET', 'POST'])
def emergency():
    if request.method == 'POST':
        emergency_type = request.form.get('emergency_type', 'police')
        message = request.form.get('message', '')
        
        # In a real application, you would connect to actual emergency services
        # This is just a simulation
        emergency_number = app.config['EMERGENCY_SERVICES'].get(emergency_type, '911')
        
        # For demo purposes, we'll just save the emergency request
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} - Emergency: {emergency_type.upper()} called. Message: {message}\n"
        
        with open('emergency_log.txt', 'a') as f:
            f.write(log_entry)
        
        flash(f"Emergency {emergency_type} alert sent to {emergency_number}", "success")
        return redirect(url_for('emergency'))
    
    return render_template('emergency.html', services=app.config['EMERGENCY_SERVICES'])

@app.route('/live_transcribe', methods=['GET', 'POST'])
def live_transcribe():
    if request.method == 'GET':
        return render_template('live_transcribe.html')
    
    try:
        data = request.get_json()
        text = data.get('text', '')
        language = data.get('language', 'en-US')

        if not text:
            return {'success': False, 'error': 'No text provided'}, 400

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"live_transcription_{timestamp}.txt"
        save_path = os.path.join(app.config['CAPTION_FOLDER'], filename)

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(text)

        return {'success': True, 'filename': filename}

    except Exception as e:
        return {'success': False, 'error': str(e)}, 500




@app.route('/mic', methods=['GET', 'POST'])
def mic():
    if request.method == 'POST':
        converter = SpeechToTextConverter()
        with sr.Microphone() as source:
            converter.recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = converter.get_audio_input(source)
            if audio:
                language = 'en-US' 
                text = converter.transcribe_audio(audio, language)  
                if text:
                    filename = converter.save_results(text, audio)
                    return render_template('mic_results.html', transcript=text, filename=filename)
            flash("Failed to capture or transcribe audio.", "error")
            return redirect(request.url)
    return render_template('mic.html', languages=languages)



@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['CAPTION_FOLDER'], filename, as_attachment=True)

@app.route('/uploads/<filename>')
def serve_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not FFMPEG_PATH:
        print("\nWarning: FFmpeg not found. Video processing will be disabled.")
    app.run(debug=True)
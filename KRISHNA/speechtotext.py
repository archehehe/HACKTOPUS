import pyttsx3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import os
import json
import logging
from gtts import gTTS
import pyperclip
import re
import PyPDF2
import docx
import platform
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import pygame

# Setup logging
logging.basicConfig(filename='speak4mepro.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class Speak4MePro:
    def __init__(self, root):
        self.root = root
        self.root.title("Speak4Me Pro")
        self.root.geometry("1000x700")
        self.engine = None
        self.voices = []
        self.current_voice = 0
        self.rate = 150
        self.volume = 1.0
        self.pitch = 0  # For SAPI5 pitch control
        self.is_speaking = False
        self.paused = False
        self.dark_mode = False
        self.learning_mode = False
        self.pronunciation_helper = False
        self.emotion_mode = 'Normal'
        self.context_mode = 'Auto'
        self.use_gtts = False
        self.speech_thread = None
        self.recorded_files = []
        self.speech_history = []
        
        self.pronunciation_dict = self.load_data('custom_pronunciations.json', {})
        self.saved_presets = self.load_data('speak4me_presets.json', [])
        self.voice_profiles = self.load_data('voice_profiles.json', [])
        self.speech_history = self.load_data('speech_history.json', [])
        
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        pygame.mixer.init()
        
        self.setup_ui()
        self.initialize_engine()
        self.update_engine_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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
                    self.voice_combobox['values'] = [v.name for v in self.voices]
                    self.voice_combobox.current(self.current_voice)
                    logging.info(f"Initialized with SAPI5 voices: {[v.name for v in self.voices]}, selected {self.voices[self.current_voice].name}")
                    return
                else:
                    logging.warning("No SAPI5 voices found, attempting gTTS fallback")
            except Exception as e:
                logging.error(f"SAPI5 init attempt {attempt+1} failed: {e}")
            
            if not self.use_gtts:
                self.use_gtts = True
                self.engine = None
                logging.info("Switching to gTTS fallback")
                return
        
        messagebox.showerror("TTS Error", "TTS initialization failed. Go to Control Panel > Speech > Text to Speech to configure voices.")
        self.engine = None

    def setup_ui(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Sidebar
        sidebar = ttk.Frame(main_container, width=200, relief=tk.RAISED)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        ttk.Label(sidebar, text="Speak4Me Pro", font=('Segoe UI', 14, 'bold')).pack(pady=10)
        ttk.Button(sidebar, text="Toggle Theme", command=self.toggle_theme).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(sidebar, text="Quick Fix TTS", command=self.fix_tts).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(sidebar, text="Clear History", command=self.clear_history).pack(fill=tk.X, padx=5, pady=5)
        
        # Main content
        content_frame = ttk.Frame(main_container)
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Notebook (Tabs)
        self.notebook = ttk.Notebook(content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Speak Tab
        speak_frame = ttk.Frame(self.notebook)
        self.notebook.add(speak_frame, text="Speak")
        
        self.text_input = tk.Text(speak_frame, wrap=tk.WORD, font=('Segoe UI', 11), padx=5, pady=5, height=10)
        self.text_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.text_input.tag_config("highlight", background="yellow")
        
        controls_frame = ttk.Frame(speak_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(controls_frame, text="Voice:").pack(side=tk.LEFT, padx=5)
        self.voice_combobox = ttk.Combobox(controls_frame, values=[v.name for v in self.voices] or ["No voices (gTTS)"], state="readonly")
        self.voice_combobox.pack(side=tk.LEFT, padx=5)
        self.voice_combobox.bind("<<ComboboxSelected>>", self.change_voice)
        
        ttk.Label(controls_frame, text="Speed:").pack(side=tk.LEFT, padx=5)
        self.rate_scale = ttk.Scale(controls_frame, from_=50, to=300, value=self.rate, command=self.update_rate)
        self.rate_scale.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(controls_frame, text="Volume:").pack(side=tk.LEFT, padx=5)
        self.volume_scale = ttk.Scale(controls_frame, from_=0, to=100, value=self.volume*100, command=self.update_volume)
        self.volume_scale.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(controls_frame, text="Pitch:").pack(side=tk.LEFT, padx=5)
        self.pitch_scale = ttk.Scale(controls_frame, from_=-10, to=10, value=self.pitch, command=self.update_pitch)
        self.pitch_scale.pack(side=tk.LEFT, padx=5)
        
        self.emotion_var = tk.StringVar(value=self.emotion_mode)
        ttk.OptionMenu(controls_frame, self.emotion_var, self.emotion_mode, *['Normal', 'Happy', 'Sad', 'Angry', 'Calm'],
                      command=self.apply_emotion).pack(side=tk.LEFT, padx=5)
        
        self.context_var = tk.StringVar(value=self.context_mode)
        ttk.OptionMenu(controls_frame, self.context_var, self.context_mode, *['Auto', 'News', 'Poetry', 'Story', 'Dialogue', 'Technical'],
                      command=self.apply_context).pack(side=tk.LEFT, padx=5)
        
        self.learning_check = ttk.Checkbutton(controls_frame, text="Learning Mode", command=self.toggle_learning)
        self.learning_check.pack(side=tk.LEFT, padx=5)
        self.pronunciation_check = ttk.Checkbutton(controls_frame, text="Pronunciation", command=self.toggle_pronunciation)
        self.pronunciation_check.pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Add Pronunciation", command=self.add_pronunciation).pack(side=tk.LEFT, padx=5)
        
        btn_frame = ttk.Frame(controls_frame)
        btn_frame.pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Speak", command=self.toggle_speech).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Stop", command=self.stop_speech).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Analyze Sentiment", command=self.analyze_sentiment).pack(side=tk.LEFT, padx=5)
        
        # Record Tab
        record_frame = ttk.Frame(self.notebook)
        self.notebook.add(record_frame, text="Record")
        
        ttk.Label(record_frame, text="Record Speech", font=('Segoe UI', 12, 'bold')).pack(pady=5)
        ttk.Button(record_frame, text="Record as MP3", command=self.record_speech).pack(pady=5)
        self.record_listbox = tk.Listbox(record_frame, height=10)
        self.record_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.record_listbox.bind('<<ListboxSelect>>', self.play_recording)
        self.update_record_listbox()
        
        # History Tab
        history_frame = ttk.Frame(self.notebook)
        self.notebook.add(history_frame, text="History")
        
        ttk.Label(history_frame, text="Speech History", font=('Segoe UI', 12, 'bold')).pack(pady=5)
        self.history_listbox = tk.Listbox(history_frame, height=10)
        self.history_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.history_listbox.bind('<<ListboxSelect>>', self.replay_history)
        self.update_history_listbox()
        
        # Settings Tab
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")
        
        ttk.Label(settings_frame, text="Settings", font=('Segoe UI', 12, 'bold')).pack(pady=5)
        ttk.Button(settings_frame, text="Clear Pronunciation Dict", command=self.clear_pronunciations).pack(pady=5)
        
        # Progress and Status
        self.progress = ttk.Progressbar(content_frame, mode='determinate')
        self.progress.pack(fill=tk.X, padx=5, pady=2)
        self.status = tk.StringVar(value="Ready")
        ttk.Label(content_frame, textvariable=self.status).pack(side=tk.BOTTOM, fill=tk.X)
        
        self.root.bind('<Return>', lambda e: self.toggle_speech())

    def configure_styles(self):
        if self.dark_mode:
            bg = '#2e2e2e'
            fg = '#ffffff'
            active_bg = '#3e3e3e'
        else:
            bg = '#f0f0f0'
            fg = '#000000'
            active_bg = '#e0e0e0'
        
        self.style.configure('.', font=('Segoe UI', 10), background=bg, foreground=fg)
        self.style.configure('TFrame', background=bg)
        self.style.configure('TLabel', background=bg, foreground=fg)
        self.style.configure('TButton', background=bg, foreground=fg)
        self.style.map('TButton', background=[('active', active_bg)])
        self.style.configure('TScale', background=bg)
        self.style.configure('TNotebook', background=bg)
        self.style.configure('TNotebook.Tab', background=bg, foreground=fg)
        self.style.map('TNotebook.Tab', background=[('selected', active_bg)])
        self.root.configure(bg=bg)

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.configure_styles()
        self.status.set(f"Theme: {'Dark' if self.dark_mode else 'Light'}")
        logging.info(f"Theme toggled to {'Dark' if self.dark_mode else 'Light'}")

    def update_engine_settings(self):
        if not self.engine and not self.use_gtts:
            self.initialize_engine()
            if not self.engine and not self.use_gtts:
                self.status.set("TTS unavailable: Check system TTS")
                return
        
        if self.voices and not self.use_gtts:
            try:
                self.engine.setProperty('voice', self.voices[self.current_voice].id)
                self.engine.setProperty('rate', max(80 if self.learning_mode else 0, self.rate))
                self.engine.setProperty('volume', self.volume)
                if self.pitch != 0:  # Pitch may not be supported
                    try:
                        self.engine.setProperty('pitch', self.pitch)
                    except Exception as e:
                        logging.warning(f"Pitch adjustment not supported: {e}")
                logging.info(f"Settings applied: voice={self.voices[self.current_voice].name}, rate={self.rate}, volume={self.volume}, pitch={self.pitch}")
            except Exception as e:
                logging.error(f"Failed to set SAPI5 properties: {e}")
                self.use_gtts = True
                self.engine = None
                self.status.set("Switched to gTTS due to SAPI5 error")
        
        self.status.set(f"Rate: {self.rate} wpm, Volume: {int(self.volume*100)}%")

    def change_voice(self, event):
        if self.voices:
            self.current_voice = self.voice_combobox.current()
            self.update_engine_settings()
            self.status.set(f"Voice: {self.voices[self.current_voice].name} (Female preferred)")
            logging.info(f"Voice changed to {self.voices[self.current_voice].name}")

    def update_rate(self, value):
        self.rate = int(float(value))
        self.update_engine_settings()
        self.status.set(f"Rate: {self.rate} wpm")

    def update_volume(self, value):
        self.volume = float(value) / 100
        self.update_engine_settings()
        self.status.set(f"Volume: {int(self.volume*100)}%")

    def update_pitch(self, value):
        if self.use_gtts:
            self.status.set("Pitch not supported with gTTS")
            return
        self.pitch = int(float(value))
        self.update_engine_settings()
        self.status.set(f"Pitch: {self.pitch}")

    def apply_emotion(self, emotion):
        if self.context_mode != 'Auto':
            self.status.set("Disable Content Type for Emotion")
            return
        self.emotion_mode = emotion
        emotions = {
            'Happy': {'rate': 180, 'volume': 1.0},
            'Sad': {'rate': 90, 'volume': 0.8},
            'Angry': {'rate': 220, 'volume': 1.1},
            'Calm': {'rate': 110, 'volume': 0.9},
            'Normal': {'rate': 150, 'volume': 1.0}
        }
        settings = emotions.get(emotion, emotions['Normal'])
        self.rate = settings['rate']
        self.volume = min(settings['volume'], 1.0)
        self.rate_scale.set(self.rate)
        self.volume_scale.set(self.volume * 100)
        self.update_engine_settings()
        self.status.set(f"Emotion: {emotion}")
        logging.info(f"Applied emotion: {emotion}, rate={self.rate}, volume={self.volume}")

    def apply_context(self, context):
        if self.emotion_mode != 'Normal':
            self.status.set("Disable Emotion for Content Type")
            return
        self.context_mode = context
        contexts = {
            'News': {'rate': 180, 'volume': 1.0, 'voice_pref': ['david', 'male']},
            'Poetry': {'rate': 100, 'volume': 0.9, 'voice_pref': ['zira', 'female']},
            'Story': {'rate': 140, 'volume': 0.9, 'voice_pref': ['zira', 'female']},
            'Dialogue': {'rate': 160, 'volume': 0.95, 'voice_pref': ['zira', 'female']},
            'Technical': {'rate': 150, 'volume': 1.0, 'voice_pref': ['david', 'male']},
            'Auto': {'rate': 150, 'volume': 1.0}
        }
        settings = contexts.get(context, contexts['Auto'])
        self.rate = settings['rate']
        self.volume = min(settings['volume'], 1.0)
        if self.voices and context != 'Auto':
            for i, voice in enumerate(self.voices):
                if any(pref in voice.name.lower() for pref in settings['voice_pref']):
                    self.current_voice = i
                    self.voice_combobox.current(i)
                    break
                elif 'female' in voice.name.lower() and 'zira' in settings['voice_pref']:
                    self.current_voice = i
                    self.voice_combobox.current(i)
            self.status.set(f"Voice: {self.voices[self.current_voice].name} (Female for {context})" if 'female' in self.voices[self.current_voice].name.lower() else f"Voice: {self.voices[self.current_voice].name}")
        self.rate_scale.set(self.rate)
        self.volume_scale.set(self.volume * 100)
        self.update_engine_settings()
        self.status.set(f"Context: {context}")
        logging.info(f"Applied context: {context}, rate={self.rate}, volume={self.volume}")

    def toggle_learning(self):
        self.learning_mode = not self.learning_mode
        self.status.set(f"Learning Mode: {'ON' if self.learning_mode else 'OFF'}")
        if self.learning_mode:
            self.rate = max(80, self.rate - 50)
            self.rate_scale.set(self.rate)
        self.update_engine_settings()
        logging.info(f"Learning Mode toggled: {self.learning_mode}")

    def toggle_pronunciation(self):
        self.pronunciation_helper = not self.pronunciation_helper
        self.status.set(f"Pronunciation: {'ON' if self.pronunciation_helper else 'OFF'}")
        logging.info(f"Pronunciation helper toggled: {self.pronunciation_helper}")

    def add_pronunciation(self):
        word = simpledialog.askstring("Pronunciation", "Enter word to customize:")
        if not word or not word.strip():
            self.status.set("Invalid word entered")
            return
        pron = simpledialog.askstring("Pronunciation", f"Pronounce '{word}' as:")
        if pron:
            self.pronunciation_dict[word.lower()] = pron
            self.save_data('custom_pronunciations.json', self.pronunciation_dict)
            self.status.set(f"Added: {word} -> {pron}")
            logging.info(f"Added pronunciation: {word} -> {pron}")
        else:
            self.status.set("No pronunciation added")

    def apply_pronunciations(self, text):
        if not self.pronunciation_helper or not text or not self.pronunciation_dict:
            return text
        original_text = text
        for word, pron in self.pronunciation_dict.items():
            if not word or not pron:
                continue
            pattern = r'\b' + re.escape(word) + r'\b'
            text = re.sub(pattern, pron, text, flags=re.IGNORECASE)
        if text != original_text:
            self.status.set("Applied custom pronunciations")
            logging.info(f"Applied pronunciations: {original_text[:50]}... -> {text[:50]}...")
        return text

    def analyze_sentiment(self):
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            self.status.set("Enter text to analyze sentiment")
            return
        scores = self.sentiment_analyzer.polarity_scores(text)
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
        self.emotion_var.set(suggested_emotion)
        self.apply_emotion(suggested_emotion)
        self.status.set(f"Sentiment: {sentiment} (Suggested Emotion: {suggested_emotion})")
        logging.info(f"Sentiment analysis: {sentiment}, compound={compound}, emotion={suggested_emotion}")

    def toggle_speech(self, event=None):
        if self.is_speaking:
            if self.paused:
                self.resume_speech()
            else:
                self.pause_speech()
        else:
            self.start_speech()

    def start_speech(self):
        text = self.apply_pronunciations(self.text_input.get("1.0", tk.END).strip())
        if not text:
            self.status.set("Enter text to speak")
            return
        
        self.is_speaking = True
        self.paused = False
        self.progress['value'] = 0
        self.speech_thread = threading.Thread(target=self.speak_text, args=(text,), daemon=True)
        self.speech_thread.start()
        self.status.set("Speaking...")
        self.speech_history.append({'text': text, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        self.save_data('speech_history.json', self.speech_history)
        self.update_history_listbox()
        logging.info("Speech started")

    def speak_text(self, text):
        if self.use_gtts:
            try:
                tts = gTTS(text=text, lang='en', slow=self.learning_mode)
                tts.save("temp.mp3")
                os.system("start temp.mp3")
                os.remove("temp.mp3")
            except Exception as e:
                self.status.set(f"gTTS error: {e}")
                logging.error(f"gTTS error: {e}")
            self.is_speaking = False
            self.progress['value'] = 100
            return
        
        if self.learning_mode:
            words = text.split()
            total_words = len(words)
            for i, word in enumerate(words):
                if not self.is_speaking or self.paused:
                    break
                self.text_input.tag_remove("highlight", "1.0", tk.END)
                start = f"1.0 + {len(' '.join(words[:i]))}c"
                end = f"{start} + {len(word)}c"
                self.text_input.tag_add("highlight", start, end)
                self.text_input.see(start)
                self.engine.say(word)
                self.engine.runAndWait()
                self.progress['value'] = (i + 1) / total_words * 100
            self.text_input.tag_remove("highlight", "1.0", tk.END)
        else:
            words = text.split()
            total_words = len(words)
            self.engine.say(text)
            self.engine.runAndWait()
            self.progress['value'] = 100
        
        if not self.paused:
            self.is_speaking = False
            self.status.set("Finished")
            logging.info("Speech completed")

    def pause_speech(self):
        if self.engine and not self.paused:
            self.engine.stop()
            self.paused = True
            self.status.set("Paused")
            logging.info("Speech paused")

    def resume_speech(self):
        if self.paused:
            self.paused = False
            self.start_speech()
            self.status.set("Resuming...")
            logging.info("Speech resumed")

    def stop_speech(self):
        if self.engine:
            self.engine.stop()
        self.is_speaking = False
        self.paused = False
        self.text_input.tag_remove("highlight", "1.0", tk.END)
        self.progress['value'] = 0
        self.status.set("Stopped")
        logging.info("Speech stopped")

    def record_speech(self):
        text = self.apply_pronunciations(self.text_input.get("1.0", tk.END).strip())
        if not text:
            self.status.set("Enter text to record")
            return
        filename = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        try:
            tts = gTTS(text=text, lang='en', slow=self.learning_mode)
            tts.save(filename)
            self.recorded_files.append(filename)
            self.update_record_listbox()
            self.status.set(f"Recorded: {filename}")
            logging.info(f"Recorded speech to {filename}")
        except Exception as e:
            self.status.set(f"Recording error: {e}")
            logging.error(f"Recording error: {e}")

    def update_record_listbox(self):
        self.record_listbox.delete(0, tk.END)
        for file in self.recorded_files:
            self.record_listbox.insert(tk.END, file)

    def play_recording(self, event):
        selection = self.record_listbox.curselection()
        if not selection:
            return
        filename = self.recorded_files[selection[0]]
        try:
            pygame.mixer.music.load(filename)
            pygame.mixer.music.play()
            self.status.set(f"Playing: {filename}")
            logging.info(f"Playing recording: {filename}")
        except Exception as e:
            self.status.set(f"Playback error: {e}")
            logging.error(f"Playback error: {e}")

    def update_history_listbox(self):
        self.history_listbox.delete(0, tk.END)
        for entry in self.speech_history:
            self.history_listbox.insert(tk.END, f"{entry['timestamp']}: {entry['text'][:50]}...")

    def replay_history(self, event):
        selection = self.history_listbox.curselection()
        if not selection:
            return
        entry = self.speech_history[selection[0]]
        self.text_input.delete("1.0", tk.END)
        self.text_input.insert("1.0", entry['text'])
        self.start_speech()
        self.notebook.select(0)  # Switch to Speak tab

    def clear_history(self):
        self.speech_history = []
        self.save_data('speech_history.json', self.speech_history)
        self.update_history_listbox()
        self.status.set("History cleared")
        logging.info("Speech history cleared")

    def clear_pronunciations(self):
        self.pronunciation_dict = {}
        self.save_data('custom_pronunciations.json', self.pronunciation_dict)
        self.status.set("Pronunciation dictionary cleared")
        logging.info("Pronunciation dictionary cleared")

    def fix_tts(self):
        if platform.system() == "Windows":
            messagebox.showinfo("Fix TTS", "Go to Control Panel > Ease of Access > Speech Recognition > Text to Speech.\nSelect a voice (e.g., Zira for female) and test with Preview Voice.\nInstall voices via Settings > Time & Language > Speech if none.")
        else:
            messagebox.showinfo("Fix TTS", "Install a TTS engine (e.g., 'espeak' on Linux) or ensure system voices are enabled.")
        self.initialize_engine()
        self.status.set("TTS rechecked")

    def on_closing(self):
        if self.engine:
            self.engine.stop()
        pygame.mixer.music.stop()
        self.save_data('custom_pronunciations.json', self.pronunciation_dict)
        self.save_data('speak4me_presets.json', self.saved_presets)
        self.save_data('voice_profiles.json', self.voice_profiles)
        self.save_data('speech_history.json', self.speech_history)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = Speak4MePro(root)
    root.mainloop()
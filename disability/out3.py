import pyttsx3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import os
import json
from datetime import datetime
from gtts import gTTS
import pyperclip
import re
import PyPDF2
import docx
import speech_recognition as sr
from PIL import Image, ImageTk
import webbrowser

class Speak4MePro:
    def __init__(self, root):
        self.root = root
        self.root.title("Speak4Me Pro - Advanced Text to Speech")
        self.root.geometry("1000x750")
        self.root.minsize(800, 600)
        
        # Initialize engine
        self.engine = pyttsx3.init()
        self.voices = self.engine.getProperty('voices')
        self.current_voice = 0
        self.rate = 150
        self.volume = 1.0
        self.is_speaking = False
        self.paused = False
        self.saved_presets = []
        self.dark_mode = False
        self.learning_mode = False
        self.pronunciation_helper = False
        self.voice_command_mode = False
        self.emotion_mode = 'Normal'
        self.context_mode = 'Auto'
        
        # Initialize features
        self.pronunciation_dict = {}
        self.voice_profiles = []
        self.accessibility_features = {
            'High Contrast': False,
            'Screen Reader Mode': False,
            'Extra Large Text': False,
            'Simplified Controls': False
        }
        
        # Supported document types
        self.supported_doc_types = [
            ('PDF Files', '*.pdf'),
            ('Word Documents', '*.docx'),
            ('Text Files', '*.txt'),
            ('eBooks', '*.epub'),
            ('All Files', '*.*')
        ]
        
        # Load data
        self.load_presets()
        self.load_pronunciation_dict()
        self.load_voice_profiles()
        
        # Setup UI
        self.setup_ui()
        
        # Find a female voice by default if available
        for i, voice in enumerate(self.voices):
            if "female" in voice.name.lower():
                self.current_voice = i
                break
        
        # Apply initial settings
        self.update_engine_settings()

    def setup_ui(self):
        # Configure modern style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        # Main container
        main_frame = ttk.Frame(self.root, padding=(15,10))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Setup menu bar
        self.setup_menu_bar()
        
        # Text input with improved styling
        text_frame = ttk.LabelFrame(main_frame, text=" Text Input ", padding=(10,5))
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0,10))
        
        self.text_input = tk.Text(text_frame, wrap=tk.WORD, 
                                font=('Segoe UI', 11), 
                                padx=10, pady=10,
                                relief=tk.FLAT,
                                highlightthickness=1,
                                highlightbackground="#ccc",
                                highlightcolor="#4a9fe0")
        self.text_input.pack(fill=tk.BOTH, expand=True)
        
        # Add modern scrollbar
        scrollbar = ttk.Scrollbar(self.text_input)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_input.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.text_input.yview)
        
        # Configure word highlight tag
        self.word_highlight_tag = "highlight"
        self.text_input.tag_config(self.word_highlight_tag, 
                                 background="yellow", 
                                 foreground="black")
        
        # Controls with better spacing
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0,10))
        
        # Voice settings frame
        voice_frame = ttk.LabelFrame(controls_frame, text=" Voice Settings ", padding=(10,5))
        voice_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Voice selection
        ttk.Label(voice_frame, text="Voice:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.voice_combobox = ttk.Combobox(voice_frame, state="readonly", font=('Segoe UI', 9))
        self.voice_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        self.voice_combobox['values'] = [voice.name for voice in self.voices]
        self.voice_combobox.current(self.current_voice)
        self.voice_combobox.bind("<<ComboboxSelected>>", self.change_voice)
        
        # Rate control
        ttk.Label(voice_frame, text="Speed:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.rate_slider = ttk.Scale(voice_frame, from_=50, to=300, value=self.rate, 
                                    command=lambda v: self.update_rate(int(float(v))))
        self.rate_slider.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        self.rate_label = ttk.Label(voice_frame, text=f"{self.rate} wpm", font=('Segoe UI', 9))
        self.rate_label.grid(row=1, column=2, padx=5, pady=2)
        
        # Volume control
        ttk.Label(voice_frame, text="Volume:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.volume_slider = ttk.Scale(voice_frame, from_=0, to=100, value=self.volume*100, 
                                      command=lambda v: self.update_volume(float(v)/100))
        self.volume_slider.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        self.volume_label = ttk.Label(voice_frame, text=f"{int(self.volume*100)}%", font=('Segoe UI', 9))
        self.volume_label.grid(row=2, column=2, padx=5, pady=2)
        
        # Emotion settings
        ttk.Label(voice_frame, text="Emotion:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.emotion_var = tk.StringVar(value='Normal')
        emotions = ['Normal', 'Happy', 'Sad', 'Angry', 'Calm']
        self.emotion_menu = ttk.OptionMenu(voice_frame, self.emotion_var, 'Normal', *emotions, 
                                         command=self.apply_emotion)
        self.emotion_menu.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)
        
        # Action buttons frame
        button_frame = ttk.Frame(controls_frame, padding=(10,5))
        button_frame.pack(side=tk.RIGHT)
        
        # Control buttons
        self.play_btn = ttk.Button(button_frame, text="Speak", command=self.toggle_speech, width=12)
        self.play_btn.pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        
        ttk.Button(button_frame, text="Stop", command=self.stop_speech, width=12).pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        ttk.Button(button_frame, text="Pause", command=self.pause_speech, width=12).pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        ttk.Button(button_frame, text="Quick Speak", command=self.create_mini_mode, width=12).pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        self.voice_command_btn = ttk.Button(button_frame, text="🎤 Voice Commands OFF", 
                                          command=self.toggle_voice_commands, width=12)
        self.voice_command_btn.pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        
        # Learning tools frame
        learning_frame = ttk.LabelFrame(controls_frame, text=" Learning Tools ", padding=(10,5))
        learning_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.learning_mode_var = tk.BooleanVar()
        ttk.Checkbutton(learning_frame, text="Learning Mode", variable=self.learning_mode_var,
                       command=self.toggle_learning_mode).pack(anchor=tk.W, pady=2)
        
        self.pronunciation_helper_var = tk.BooleanVar()
        ttk.Checkbutton(learning_frame, text="Pronunciation Helper", 
                       variable=self.pronunciation_helper_var,
                       command=self.toggle_pronunciation_helper).pack(anchor=tk.W, pady=2)
        
        ttk.Button(learning_frame, text="Add Custom Pronunciation",
                  command=self.add_custom_pronunciation).pack(fill=tk.X, pady=2)
        
        # Context awareness frame
        context_frame = ttk.LabelFrame(controls_frame, text=" Content Type ", padding=(10,5))
        context_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.context_var = tk.StringVar(value='Auto')
        contexts = ['Auto', 'News', 'Story', 'Technical', 'Dialogue']
        self.context_menu = ttk.OptionMenu(context_frame, self.context_var, 'Auto', *contexts,
                                         command=self.apply_context_style)
        self.context_menu.pack(fill=tk.X, pady=2)
        
        ttk.Button(context_frame, text="Detect Content Type",
                  command=self.detect_content_type).pack(fill=tk.X, pady=2)
        
        # File operations frame
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0,10))
        
        # File operation buttons
        ttk.Button(file_frame, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Open Document", command=self.open_document).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save Text", command=self.save_text).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Export MP3", command=self.save_as_mp3).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Paste Clipboard", command=self.read_clipboard).pack(side=tk.LEFT, padx=5)
        
        # Presets controls
        self.preset_combobox = ttk.Combobox(file_frame, state="readonly", width=20, font=('Segoe UI', 9))
        self.preset_combobox.pack(side=tk.LEFT, padx=5)
        self.update_presets_dropdown()
        ttk.Button(file_frame, text="Load Preset", command=self.load_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save Preset", command=self.save_preset).pack(side=tk.LEFT, padx=5)
        
        # Voice profiles
        self.profile_combobox = ttk.Combobox(file_frame, state="readonly", width=20, font=('Segoe UI', 9))
        self.profile_combobox.pack(side=tk.LEFT, padx=5)
        self.update_voice_profiles_dropdown()
        ttk.Button(file_frame, text="Load Profile", command=self.apply_voice_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="New Profile", command=self.create_voice_profile).pack(side=tk.LEFT, padx=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0,10))
        
        # Status bar
        status_frame = ttk.Frame(main_frame, relief=tk.SUNKEN)
        status_frame.pack(fill=tk.X)
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        ttk.Label(status_frame, textvariable=self.status_var, 
                 padding=(5,2,5,2), 
                 anchor=tk.W).pack(fill=tk.X)
        
        # Configure initial dark mode state
        self.toggle_dark_mode()

    def configure_styles(self):
        """Configure modern styles for widgets"""
        self.style.configure('.', font=('Segoe UI', 9))
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0', font=('Segoe UI', 9))
        self.style.configure('TButton', font=('Segoe UI', 9), padding=5)
        self.style.configure('TEntry', padding=5)
        self.style.configure('TCombobox', padding=5)
        self.style.map('TButton', 
                      foreground=[('active', '!disabled', 'black')],
                      background=[('active', '#e1e1e1')])
        self.style.configure('TLabelframe.Label', font=('Segoe UI', 9, 'bold'))
        self.style.configure('Horizontal.TProgressbar', thickness=6)

    def setup_menu_bar(self):
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Text File", command=self.open_file)
        file_menu.add_command(label="Open Document", command=self.open_document)
        file_menu.add_command(label="Save Text", command=self.save_text)
        file_menu.add_command(label="Export as MP3", command=self.save_as_mp3)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Paste Clipboard", command=self.read_clipboard)
        edit_menu.add_command(label="Clear Text", command=self.clear_text)
        edit_menu.add_separator()
        edit_menu.add_command(label="Add Custom Pronunciation", command=self.add_custom_pronunciation)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Accessibility menu
        accessibility_menu = tk.Menu(menubar, tearoff=0)
        for feature in self.accessibility_features:
            accessibility_menu.add_checkbutton(
                label=feature,
                command=lambda f=feature: self.toggle_accessibility(f)
            )
        menubar.add_cascade(label="Accessibility", menu=accessibility_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="User Guide", command=self.show_user_guide)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)

    def update_engine_settings(self):
        self.engine.setProperty('voice', self.voices[self.current_voice].id)
        self.engine.setProperty('rate', self.rate)
        self.engine.setProperty('volume', self.volume)
        
        # Apply emotion settings if not normal
        if self.emotion_mode != 'Normal':
            self.apply_emotion(self.emotion_mode)
        
        # Apply learning mode if active
        if self.learning_mode:
            self.engine.setProperty('rate', max(100, self.rate - 50))

    def change_voice(self, event=None):
        self.current_voice = self.voice_combobox.current()
        self.update_engine_settings()
        self.update_status(f"Voice changed to {self.voices[self.current_voice].name}")
        self.preview_voice()
    
    def update_rate(self, rate):
        self.rate = rate
        self.rate_label.config(text=f"{rate} wpm")
        self.update_engine_settings()
        self.preview_voice()
    
    def update_volume(self, volume):
        self.volume = volume
        self.volume_label.config(text=f"{int(volume*100)}%")
        self.update_engine_settings()
        self.preview_voice()
    
    def toggle_speech(self):
        if self.is_speaking and not self.paused:
            self.pause_speech()
        elif self.is_speaking and self.paused:
            self.resume_speech()
        else:
            self.start_speech()
    
    def start_speech(self):
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "Please enter some text to speak.")
            return
        
        self.is_speaking = True
        self.paused = False
        self.play_btn.config(text="Pause")
        
        # Apply custom pronunciations if enabled
        if self.pronunciation_helper:
            text = self.apply_custom_pronunciations(text)
        
        # Start speech in a separate thread
        threading.Thread(target=self.speak_text, args=(text,), daemon=True).start()
        self.update_status("Speaking...")
    
    def pause_speech(self):
        if self.is_speaking and not self.paused:
            self.engine.stop()
            self.paused = True
            self.play_btn.config(text="Resume")
            self.update_status("Paused")
    
    def resume_speech(self):
        if self.is_speaking and self.paused:
            self.paused = False
            self.play_btn.config(text="Pause")
            text = self.text_input.get("1.0", tk.END).strip()
            threading.Thread(target=self.speak_text, args=(text,), daemon=True).start()
            self.update_status("Resuming speech...")
    
    def stop_speech(self):
        self.engine.stop()
        self.is_speaking = False
        self.paused = False
        self.play_btn.config(text="Speak")
        self.update_status("Ready")
        self.progress['value'] = 0
    
    def speak_text(self, text):
        words = text.split()
        total_words = len(words)
        
        def update_progress(i):
            progress = (i / total_words) * 100
            self.progress['value'] = progress
            self.root.update_idletasks()
        
        for i, word in enumerate(words):
            if not self.is_speaking or self.paused:
                break
            
            # Get word position for highlighting
            start_pos = f"1.0 + {len(' '.join(words[:i]))} chars"
            end_pos = f"{start_pos} + {len(word)} chars"
            
            # Highlight current word if in learning mode
            if self.learning_mode:
                self.highlight_current_word(word, start_pos, end_pos)
            
            self.engine.say(word)
            self.engine.runAndWait()
            update_progress(i)
        
        self.progress['value'] = 0
        if not self.paused:
            self.is_speaking = False
            self.play_btn.config(text="Speak")
            self.update_status("Finished speaking")
    
    def preview_voice(self):
        if self.is_speaking:
            return
        
        # Save current text
        current_text = self.text_input.get("1.0", tk.END).strip()
        
        # Insert preview text at cursor position
        self.text_input.insert(tk.INSERT, " [Voice preview]")
        
        # Speak in a thread
        threading.Thread(
            target=lambda: (
                self.engine.say("This is how I sound now"),
                self.engine.runAndWait(),
                self.text_input.after(100, lambda: self.text_input.delete("1.0", tk.END)),
                self.text_input.after(150, lambda: self.text_input.insert("1.0", current_text))
            ),
            daemon=True
        ).start()
    
    def open_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.text_input.delete("1.0", tk.END)
                    self.text_input.insert("1.0", f.read())
                self.update_status(f"Loaded file: {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file:\n{str(e)}")
    
    def save_text(self):
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "There's no text to save.")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.update_status(f"Text saved to: {os.path.basename(filepath)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{str(e)}")
    
    def save_as_mp3(self):
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("No Text", "Please enter text first!")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3 Files", "*.mp3")]
        )
        if filepath:
            try:
                self.update_status("Converting to MP3...")
                tts = gTTS(text, lang='en')
                tts.save(filepath)
                self.update_status(f"Saved as MP3: {os.path.basename(filepath)}")
                messagebox.showinfo("Success", "MP3 file saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save MP3:\n{str(e)}")
    
    def read_clipboard(self):
        try:
            clipboard_text = pyperclip.paste()
            if clipboard_text.strip():
                self.text_input.delete("1.0", tk.END)
                self.text_input.insert("1.0", clipboard_text)
                self.update_status("Clipboard content loaded")
            else:
                messagebox.showinfo("Empty", "Clipboard is empty or contains no text.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read clipboard:\n{str(e)}")
    
    def clear_text(self):
        self.text_input.delete("1.0", tk.END)
        self.update_status("Text cleared")
    
    def load_presets(self):
        try:
            if os.path.exists('speak4me_presets.json'):
                with open('speak4me_presets.json', 'r') as f:
                    self.saved_presets = json.load(f)
        except Exception as e:
            messagebox.showwarning("Preset Error", f"Could not load presets:\n{str(e)}")
            self.saved_presets = []

    def save_presets_to_file(self):
        try:
            with open('speak4me_presets.json', 'w') as f:
                json.dump(self.saved_presets, f, indent=2)
        except Exception as e:
            messagebox.showwarning("Preset Error", f"Could not save presets:\n{str(e)}")

    def save_preset(self):
        preset_name = simpledialog.askstring("Save Preset", "Enter a name for this preset:")
        if preset_name:
            preset = {
                'name': preset_name,
                'voice_index': self.current_voice,
                'rate': self.rate,
                'volume': self.volume,
                'emotion': self.emotion_mode,
                'context': self.context_mode,
                'timestamp': datetime.now().isoformat()
            }
            
            # Check if preset already exists
            existing_index = next((i for i, p in enumerate(self.saved_presets) 
                              if p['name'].lower() == preset_name.lower()), None)
            
            if existing_index is not None:
                self.saved_presets[existing_index] = preset
            else:
                self.saved_presets.append(preset)
            
            self.save_presets_to_file()
            self.update_presets_dropdown()
            self.update_status(f"Preset '{preset_name}' saved")

    def load_preset(self):
        selected = self.preset_combobox.current()
        if selected >= 0 and selected < len(self.saved_presets):
            preset = self.saved_presets[selected]
            self.current_voice = preset['voice_index']
            self.rate = preset['rate']
            self.volume = preset['volume']
            self.emotion_mode = preset.get('emotion', 'Normal')
            self.context_mode = preset.get('context', 'Auto')
            
            # Update UI controls
            self.voice_combobox.current(self.current_voice)
            self.rate_slider.set(self.rate)
            self.volume_slider.set(self.volume * 100)
            self.emotion_var.set(self.emotion_mode)
            self.context_var.set(self.context_mode)
            self.rate_label.config(text=f"{self.rate} wpm")
            self.volume_label.config(text=f"{int(self.volume*100)}%")
            
            self.update_engine_settings()
            self.update_status(f"Loaded preset: {preset['name']}")
            self.preview_voice()

    def update_presets_dropdown(self):
        self.preset_combobox['values'] = [p['name'] for p in self.saved_presets]
        if self.saved_presets:
            self.preset_combobox.current(0)
    
    def apply_emotion(self, emotion):
        self.emotion_mode = emotion
        emotions = {
            'Happy': {'rate': 180, 'pitch': 120, 'volume': 1.0},
            'Sad': {'rate': 90, 'pitch': 80, 'volume': 0.8},
            'Angry': {'rate': 220, 'pitch': 110, 'volume': 1.1},
            'Calm': {'rate': 110, 'pitch': 90, 'volume': 0.9},
            'Normal': {'rate': self.rate, 'pitch': 100, 'volume': self.volume}
        }
        
        if emotion in emotions:
            settings = emotions[emotion]
            self.engine.setProperty('rate', settings['rate'])
            self.engine.setProperty('volume', settings['volume'])
            try:
                self.engine.setProperty('pitch', settings['pitch'])
            except:
                pass  # Some engines may not support pitch
            
            self.update_status(f"Emotion set to {emotion}")
            self.preview_voice()
    
    def toggle_learning_mode(self):
        self.learning_mode = self.learning_mode_var.get()
        if self.learning_mode:
            self.update_status("Learning mode: Slower speech with clearer pronunciation")
            self.engine.setProperty('rate', max(100, self.rate - 50))
        else:
            self.engine.setProperty('rate', self.rate)
            self.update_status("Learning mode deactivated")
    
    def toggle_pronunciation_helper(self):
        self.pronunciation_helper = self.pronunciation_helper_var.get()
        status = "ON" if self.pronunciation_helper else "OFF"
        self.update_status(f"Pronunciation helper {status}")
    
    def highlight_current_word(self, word, start_pos, end_pos):
        self.text_input.tag_remove(self.word_highlight_tag, "1.0", tk.END)
        self.text_input.tag_add(self.word_highlight_tag, start_pos, end_pos)
        self.text_input.see(start_pos)
        self.root.update()
    
    def add_custom_pronunciation(self):
        word = simpledialog.askstring("Custom Pronunciation", "Enter word to customize:")
        if word:
            pronunciation = simpledialog.askstring("Custom Pronunciation", 
                                                 f"Enter phonetic pronunciation for '{word}':")
            if pronunciation:
                self.pronunciation_dict[word.lower()] = pronunciation
                self.save_pronunciation_dict()
                messagebox.showinfo("Success", f"'{word}' will now be pronounced as '{pronunciation}'")
    
    def apply_custom_pronunciations(self, text):
        for word, pronunciation in self.pronunciation_dict.items():
            text = re.sub(r'\b' + re.escape(word) + r'\b', pronunciation, text, flags=re.IGNORECASE)
        return text
    
    def load_pronunciation_dict(self):
        try:
            if os.path.exists('custom_pronunciations.json'):
                with open('custom_pronunciations.json', 'r') as f:
                    self.pronunciation_dict = json.load(f)
        except Exception as e:
            messagebox.showwarning("Pronunciation Error", f"Could not load pronunciations:\n{str(e)}")
            self.pronunciation_dict = {}
    
    def save_pronunciation_dict(self):
        try:
            with open('custom_pronunciations.json', 'w') as f:
                json.dump(self.pronunciation_dict, f, indent=2)
        except Exception as e:
            messagebox.showwarning("Pronunciation Error", f"Could not save pronunciations:\n{str(e)}")
    
    def detect_content_type(self):
        text = self.text_input.get("1.0", tk.END)[:500]  # Analyze first 500 chars
        if any(keyword in text.lower() for keyword in ['chapter', 'story', 'tale']):
            self.context_var.set('Story')
        elif any(keyword in text.lower() for keyword in ['research', 'data', 'analysis']):
            self.context_var.set('Technical')
        elif any(keyword in text.lower() for keyword in ['said', 'replied', 'asked']):
            self.context_var.set('Dialogue')
        else:
            self.context_var.set('News')
        self.apply_context_style()
    
    def apply_context_style(self, *args):
        context = self.context_var.get()
        if context == 'Auto':
            self.detect_content_type()
            return
        
        context_styles = {
            'News': {'rate': 170, 'pitch': 100, 'volume': 1.0},
            'Story': {'rate': 130, 'pitch': 95, 'volume': 0.9},
            'Technical': {'rate': 150, 'pitch': 105, 'volume': 1.0},
            'Dialogue': {'rate': 160, 'pitch': 110, 'volume': 1.0}
        }
        
        if context in context_styles:
            settings = context_styles[context]
            self.rate = settings['rate']
            self.volume = settings['volume']
            
            # Update UI controls
            self.rate_slider.set(self.rate)
            self.volume_slider.set(self.volume * 100)
            self.rate_label.config(text=f"{self.rate} wpm")
            self.volume_label.config(text=f"{int(self.volume*100)}%")
            
            self.update_engine_settings()
            self.update_status(f"Content type set to {context}")
            self.preview_voice()
    
    def create_voice_profile(self):
        name = simpledialog.askstring("Voice Profile", "Enter profile name:")
        if name:
            profile = {
                'name': name,
                'rate': self.rate,
                'volume': self.volume,
                'voice': self.current_voice,
                'emotion': self.emotion_mode,
                'timestamp': datetime.now().isoformat()
            }
            self.voice_profiles.append(profile)
            self.save_voice_profiles()
            self.update_voice_profiles_dropdown()
            messagebox.showinfo("Success", f"Voice profile '{name}' created!")
    
    def apply_voice_profile(self):
        selected = self.profile_combobox.current()
        if selected >= 0 and selected < len(self.voice_profiles):
            profile = self.voice_profiles[selected]
            self.current_voice = profile['voice']
            self.rate = profile['rate']
            self.volume = profile['volume']
            self.emotion_mode = profile.get('emotion', 'Normal')
            
            # Update UI controls
            self.voice_combobox.current(self.current_voice)
            self.rate_slider.set(self.rate)
            self.volume_slider.set(self.volume * 100)
            self.emotion_var.set(self.emotion_mode)
            self.rate_label.config(text=f"{self.rate} wpm")
            self.volume_label.config(text=f"{int(self.volume*100)}%")
            
            self.update_engine_settings()
            self.update_status(f"Loaded voice profile: {profile['name']}")
            self.preview_voice()
    
    def update_voice_profiles_dropdown(self):
        self.profile_combobox['values'] = [p['name'] for p in self.voice_profiles]
        if self.voice_profiles:
            self.profile_combobox.current(0)
    
    def load_voice_profiles(self):
        try:
            if os.path.exists('voice_profiles.json'):
                with open('voice_profiles.json', 'r') as f:
                    self.voice_profiles = json.load(f)
        except Exception as e:
            messagebox.showwarning("Profile Error", f"Could not load voice profiles:\n{str(e)}")
            self.voice_profiles = []
    
    def save_voice_profiles(self):
        try:
            with open('voice_profiles.json', 'w') as f:
                json.dump(self.voice_profiles, f, indent=2)
        except Exception as e:
            messagebox.showwarning("Profile Error", f"Could not save voice profiles:\n{str(e)}")
    
    def toggle_accessibility(self, feature):
        self.accessibility_features[feature] = not self.accessibility_features[feature]
        
        if feature == 'High Contrast':
            self.apply_high_contrast()
        elif feature == 'Screen Reader Mode':
            self.toggle_screen_reader_mode()
        elif feature == 'Extra Large Text':
            self.apply_large_text()
        elif feature == 'Simplified Controls':
            self.simplify_controls()
        
        status = "activated" if self.accessibility_features[feature] else "deactivated"
        self.update_status(f"Accessibility: {feature} {status}")
    
    def apply_high_contrast(self):
        if self.accessibility_features['High Contrast']:
            self.text_input.configure(
                bg='black', fg='yellow',
                selectbackground='yellow', selectforeground='black',
                highlightbackground='yellow', highlightcolor='yellow'
            )
            self.style.configure('.', foreground='yellow', background='black')
            self.style.configure('TFrame', background='black')
            self.style.configure('TLabel', background='black', foreground='yellow')
            self.style.configure('TButton', background='black', foreground='yellow')
        else:
            self.toggle_dark_mode()  # Revert to current dark/light mode
    
    def toggle_screen_reader_mode(self):
        if self.accessibility_features['Screen Reader Mode']:
            # Add screen reader enhancements
            self.text_input.configure(font=('Arial', 12))
            self.play_btn.focus_set()
        else:
            # Revert to normal settings
            self.text_input.configure(font=('Segoe UI', 11))
    
    def apply_large_text(self):
        if self.accessibility_features['Extra Large Text']:
            self.style.configure('.', font=('Segoe UI', 14))
            self.text_input.configure(font=('Segoe UI', 14))
        else:
            self.style.configure('.', font=('Segoe UI', 9))
            self.text_input.configure(font=('Segoe UI', 11))
    
    def simplify_controls(self):
        if self.accessibility_features['Simplified Controls']:
            # Hide advanced controls and show only basic ones
            for widget in self.root.winfo_children():
                if isinstance(widget, (ttk.LabelFrame, ttk.Combobox)):
                    widget.pack_forget()
            self.play_btn.pack(side=tk.LEFT, padx=5)
        else:
            # Restore all controls
            self.setup_ui()
    
    def open_document(self):
        filepath = filedialog.askopenfilename(filetypes=self.supported_doc_types)
        if filepath:
            try:
                text = ""
                if filepath.lower().endswith('.pdf'):
                    text = self.extract_text_from_pdf(filepath)
                elif filepath.lower().endswith(('.docx', '.doc')):
                    text = self.extract_text_from_docx(filepath)
                elif filepath.lower().endswith('.txt'):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        text = f.read()
                else:
                    messagebox.showwarning("Unsupported", "Document format not supported")
                    return
                
                self.text_input.delete("1.0", tk.END)
                self.text_input.insert("1.0", text)
                self.update_status(f"Loaded document: {os.path.basename(filepath)}")
                self.detect_content_type()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read document:\n{str(e)}")
    
    def extract_text_from_pdf(self, filepath):
        text = ""
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def extract_text_from_docx(self, filepath):
        doc = docx.Document(filepath)
        return "\n".join([para.text for para in doc.paragraphs])
    
    def toggle_voice_commands(self):
        self.voice_command_mode = not self.voice_command_mode
        if self.voice_command_mode:
            self.voice_command_btn.config(text="🎤 Voice Commands ON (Listening...)")
            threading.Thread(target=self.listen_for_commands, daemon=True).start()
        else:
            self.voice_command_btn.config(text="🎤 Voice Commands OFF")
    
    def listen_for_commands(self):
        r = sr.Recognizer()
        
        while self.voice_command_mode:
            try:
                with sr.Microphone() as source:
                    self.update_status("Listening for voice commands...")
                    audio = r.listen(source, timeout=3, phrase_time_limit=3)
                command = r.recognize_google(audio).lower()
                self.update_status(f"Heard: {command}")
                
                commands = {
                    'start reading': self.start_speech,
                    'stop reading': self.stop_speech,
                    'pause reading': self.pause_speech,
                    'resume reading': self.resume_speech,
                    'increase speed': lambda: self.update_rate(min(300, self.rate + 20)),
                    'decrease speed': lambda: self.update_rate(max(50, self.rate - 20)),
                    'louder': lambda: self.update_volume(min(1.0, self.volume + 0.1)),
                    'quieter': lambda: self.update_volume(max(0.1, self.volume - 0.1))
                }
                
                for cmd, action in commands.items():
                    if cmd in command:
                        self.root.after(0, action)
                        self.update_status(f"Executing: {cmd}")
                        break
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                self.update_status("Could not understand command")
                continue
            except Exception as e:
                self.update_status(f"Voice command error: {str(e)}")
                continue
    
    def create_mini_mode(self):
        mini_win = tk.Toplevel(self.root)
        mini_win.title("Speak4Me Quick")
        mini_win.geometry("350x180")
        
        # Apply dark mode if active
        if self.dark_mode:
            mini_win.configure(bg='#2d2d2d')
            text_color = 'white'
            entry_bg = '#3d3d3d'
        else:
            text_color = 'black'
            entry_bg = 'white'
        
        ttk.Label(mini_win, text="Enter text to speak:").pack(pady=(10,5))
        
        entry = ttk.Entry(mini_win, width=40, font=('Segoe UI', 10))
        entry.pack(pady=5, padx=10)
        entry.focus()
        
        def speak_and_close():
            text = entry.get()
            if text:
                self.engine.say(text)
                self.engine.runAndWait()
            mini_win.destroy()
        
        btn_frame = ttk.Frame(mini_win)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Speak", command=speak_and_close).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="Close", command=mini_win.destroy).pack(side=tk.LEFT, padx=10)
    
    def toggle_dark_mode(self):
        if self.dark_mode:
            # Light mode colors
            bg_color = '#f0f0f0'
            text_color = 'black'
            entry_bg = 'white'
            highlight_color = '#4a9fe0'
            self.style.theme_use('clam')
        else:
            # Dark mode colors
            bg_color = '#2d2d2d'
            text_color = 'white'
            entry_bg = '#3d3d3d'
            highlight_color = '#5a9fe0'
            self.style.theme_use('alt')
        
        # Apply colors to widgets
        self.root.configure(bg=bg_color)
        self.style.configure('.', background=bg_color, foreground=text_color)
        self.style.configure('TFrame', background=bg_color)
        self.style.configure('TLabel', background=bg_color, foreground=text_color)
        self.style.configure('TButton', background=bg_color, foreground=text_color)
        self.style.configure('TEntry', fieldbackground=entry_bg, foreground=text_color)
        self.style.configure('TCombobox', fieldbackground=entry_bg, foreground=text_color)
        
        # Update text widget colors
        self.text_input.configure(
            bg=entry_bg,
            fg=text_color,
            insertbackground=text_color,
            highlightbackground=highlight_color,
            highlightcolor=highlight_color
        )
        
        self.dark_mode = not self.dark_mode
        self.update_status("Dark mode activated" if self.dark_mode else "Light mode activated")
    
    def show_user_guide(self):
        guide = """Speak4Me Pro User Guide

1. Basic Usage:
- Enter text and click Speak
- Use Pause/Resume to control playback
- Adjust speed and volume with sliders

2. Advanced Features:
- Emotion Mode: Change voice tone
- Learning Mode: Slower, clearer speech
- Pronunciation Helper: Add custom pronunciations
- Voice Profiles: Save favorite voice settings
- Content Detection: Auto-adjusts for different text types

3. Accessibility:
- High Contrast mode
- Screen Reader enhancements
- Large text options
- Simplified interface

4. Voice Commands:
Say "start reading", "pause reading", etc.
"""
        messagebox.showinfo("User Guide", guide)
    
    def show_about(self):
        about_text = """Speak4Me Pro - Advanced Text to Speech
        
Version: 3.0
Developed for Hackathon Project

Features:
- Multiple voice support
- Adjustable speed and volume
- Emotion modulation
- Learning tools
- Document integration
- Voice command control
- Dark/Light theme
- Word-by-word progress tracking
- Accessibility features"""
        
        messagebox.showinfo("About Speak4Me Pro", about_text)
    
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk()
    app = Speak4MePro(root)
    root.mainloop()
import pyttsx3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import os
import json
from datetime import datetime
from gtts import gTTS
import pyperclip
import webbrowser
from PIL import Image, ImageTk
import requests
from io import BytesIO

class BE_MY_VOICE:
    def __init__(self, root):
        self.root = root
        self.root.title("BE MY VOICE - Advanced Text to Speech (India Edition)")
        self.root.geometry("950x700")
        self.root.minsize(750, 550)
        
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
        self.current_language = 'en'  # Default to English
        
        # Indian language options
        self.indian_languages = {
            'English': 'en',
            'Hindi': 'hi',
            'Bengali': 'bn',
            'Telugu': 'te',
            'Tamil': 'ta',
            'Marathi': 'mr',
            'Gujarati': 'gu',
            'Kannada': 'kn',
            'Malayalam': 'ml',
            'Punjabi': 'pa',
            'Odia': 'or',
            'Urdu': 'ur'
        }
        
        # Indian English accent options
        self.indian_accents = {
            'Standard Indian': 'com',
            'South Indian': 'co.in',
            'North Indian': 'co.in',
            'East Indian': 'co.in',
            'West Indian': 'co.in'
        }
        
        # Load presets
        self.load_presets()
        
        # Setup UI
        self.setup_ui()
        
        # Find a female Indian English voice by default if available
        for i, voice in enumerate(self.voices):
            if "india" in voice.name.lower() or "indian" in voice.name.lower():
                self.current_voice = i
                break
        
        # Apply initial settings
        self.update_engine_settings()

    def setup_ui(self):
        # Configure modern style with Indian color scheme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        # Main container
        main_frame = ttk.Frame(self.root, padding=(15,10))
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Setup menu bar
        self.setup_menu_bar()
        
        # Add Indian-themed header
        self.setup_indian_header(main_frame)
        
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
        
        # Controls with better spacing
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(0,10))
        
        # Voice settings frame
        voice_frame = ttk.LabelFrame(controls_frame, text=" Voice Settings ", padding=(10,5))
        voice_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Language selection (Indian languages)
        ttk.Label(voice_frame, text="Language:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.language_combobox = ttk.Combobox(voice_frame, values=list(self.indian_languages.keys()), 
                                            state="readonly", font=('Segoe UI', 9))
        self.language_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        self.language_combobox.current(0)
        self.language_combobox.bind("<<ComboboxSelected>>", self.change_language)
        
        # Indian English accent selection
        ttk.Label(voice_frame, text="Indian Accent:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.accent_combobox = ttk.Combobox(voice_frame, values=list(self.indian_accents.keys()), 
                                           state="readonly", font=('Segoe UI', 9))
        self.accent_combobox.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        self.accent_combobox.current(0)
        self.accent_combobox.bind("<<ComboboxSelected>>", self.change_accent)
        
        # Voice selection
        ttk.Label(voice_frame, text="Voice:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.voice_combobox = ttk.Combobox(voice_frame, state="readonly", font=('Segoe UI', 9))
        self.voice_combobox.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        self.voice_combobox['values'] = [voice.name for voice in self.voices]
        self.voice_combobox.current(self.current_voice)
        self.voice_combobox.bind("<<ComboboxSelected>>", self.change_voice)
        
        # Rate control
        ttk.Label(voice_frame, text="Speed:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.rate_slider = ttk.Scale(voice_frame, from_=50, to=300, value=self.rate, 
                                    command=lambda v: self.update_rate(int(float(v))))
        self.rate_slider.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)
        self.rate_label = ttk.Label(voice_frame, text=f"{self.rate} wpm", font=('Segoe UI', 9))
        self.rate_label.grid(row=3, column=2, padx=5, pady=2)
        
        # Volume control
        ttk.Label(voice_frame, text="Volume:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.volume_slider = ttk.Scale(voice_frame, from_=0, to=100, value=self.volume*100, 
                                      command=lambda v: self.update_volume(float(v)/100))
        self.volume_slider.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)
        self.volume_label = ttk.Label(voice_frame, text=f"{int(self.volume*100)}%", font=('Segoe UI', 9))
        self.volume_label.grid(row=4, column=2, padx=5, pady=2)
        
        # Action buttons frame
        button_frame = ttk.Frame(controls_frame, padding=(10,5))
        button_frame.pack(side=tk.RIGHT)
        
        # Control buttons with Indian color scheme
        self.play_btn = ttk.Button(button_frame, text="Speak", command=self.toggle_speech, width=12)
        self.play_btn.pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        
        ttk.Button(button_frame, text="Stop", command=self.stop_speech, width=12).pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        ttk.Button(button_frame, text="Pause", command=self.pause_speech, width=12).pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        ttk.Button(button_frame, text="Quick Speak", command=self.create_mini_mode, width=12).pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        ttk.Button(button_frame, text="Learn English", command=self.open_english_learning, width=12).pack(side=tk.TOP, padx=5, pady=2, fill=tk.X)
        
        # File operations frame
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=(0,10))
        
        # File operation buttons
        ttk.Button(file_frame, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save Text", command=self.save_text).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Export MP3", command=self.save_as_mp3).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Paste Clipboard", command=self.read_clipboard).pack(side=tk.LEFT, padx=5)
        
        # Presets controls
        self.preset_combobox = ttk.Combobox(file_frame, state="readonly", width=25, font=('Segoe UI', 9))
        self.preset_combobox.pack(side=tk.LEFT, padx=5)
        self.update_presets_dropdown()
        ttk.Button(file_frame, text="Load Preset", command=self.load_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save Preset", command=self.save_preset).pack(side=tk.LEFT, padx=5)
        
        # Progress bar with Indian flag colors
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.pack(fill=tk.X, pady=(0,10))
        
        # Status bar
        status_frame = ttk.Frame(main_frame, relief=tk.SUNKEN)
        status_frame.pack(fill=tk.X)
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - BE MY VOICE India Edition")
        ttk.Label(status_frame, textvariable=self.status_var, 
                 padding=(5,2,5,2), 
                 anchor=tk.W).pack(fill=tk.X)

    def setup_indian_header(self, parent):
        """Add an Indian-themed header with flag colors"""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=tk.X, pady=(0,10))
        
        # Try to load Indian flag image
        try:
            response = requests.get("https://t3.ftcdn.net/jpg/02/58/24/10/360_F_258241066_KJeOZMUw4kjWh8c4rbJmTRsFx9wwOVYY.jpg")
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            img = img.resize((80, 50), Image.LANCZOS)
            self.flag_img = ImageTk.PhotoImage(img)
            flag_label = ttk.Label(header_frame, image=self.flag_img)
            flag_label.pack(side=tk.LEFT, padx=10)
        except:
            # Fallback if image can't be loaded
            pass
        
        # Add title with Indian colors
        title_frame = ttk.Frame(header_frame)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(title_frame, text="BE MY VOICE", 
                 font=('Segoe UI', 16, 'bold'), 
                 foreground='#FF9933').pack(side=tk.TOP, anchor=tk.W)
        ttk.Label(title_frame, text="India Edition", 
                 font=('Segoe UI', 12), 
                 foreground='#138808').pack(side=tk.TOP, anchor=tk.W)
        
        # Add quick access buttons
        btn_frame = ttk.Frame(header_frame)
        btn_frame.pack(side=tk.RIGHT, padx=10)
        
        ttk.Button(btn_frame, text="UPI Payment for Pro Mode", command=self.open_upi_payment, 
                  style='Indian.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Hindi Tutorial", command=self.open_hindi_tutorial, 
                  style='Indian.TButton').pack(side=tk.LEFT, padx=2)

    def configure_styles(self):
        """Configure modern styles with Indian color scheme"""
        self.style.configure('.', font=('Segoe UI', 9))
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', background='#f0f0f0', font=('Segoe UI', 9))
        self.style.configure('TButton', font=('Segoe UI', 9), padding=5)
        self.style.configure('TEntry', padding=5)
        self.style.configure('TCombobox', padding=5)
        
        # Indian-themed button style
        self.style.configure('Indian.TButton', 
                           foreground='white',
                           background='#FF9933',  # Saffron
                           font=('Segoe UI', 9, 'bold'))
        self.style.map('Indian.TButton',
                      background=[('active', '#138808')])  # Green when active
        
        self.style.map('TButton', 
                      foreground=[('active', '!disabled', 'black')],
                      background=[('active', '#e1e1e1')])
        self.style.configure('TLabelframe.Label', font=('Segoe UI', 9, 'bold'))
        self.style.configure('Horizontal.TProgressbar', thickness=6)

    def setup_menu_bar(self):
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save Text", command=self.save_text)
        file_menu.add_command(label="Export as MP3", command=self.save_as_mp3)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Paste Clipboard", command=self.read_clipboard)
        edit_menu.add_command(label="Clear Text", command=self.clear_text)
        edit_menu.add_command(label="Translate to Hindi", command=self.translate_to_hindi)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # Indian Languages menu
        lang_menu = tk.Menu(menubar, tearoff=0)
        for lang in self.indian_languages:
            lang_menu.add_command(label=lang, 
                                command=lambda l=lang: self.set_language(l))
        menubar.add_cascade(label="Indian Languages", menu=lang_menu)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        menubar.add_cascade(label="View", menu=view_menu)
        
        # Help menu with Indian support options
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Customer Support (India)", command=self.open_indian_support)
        help_menu.add_command(label="Buy Pro Version", command=self.open_indian_payment)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)

    def update_engine_settings(self):
        self.engine.setProperty('voice', self.voices[self.current_voice].id)
        self.engine.setProperty('rate', self.rate)
        self.engine.setProperty('volume', self.volume)
    
    def change_voice(self, event):
        self.current_voice = self.voice_combobox.current()
        self.update_engine_settings()
        self.update_status(f"Voice changed to {self.voices[self.current_voice].name}")
        self.preview_voice()
    
    def change_language(self, event):
        lang_name = self.language_combobox.get()
        self.current_language = self.indian_languages.get(lang_name, 'en')
        self.update_status(f"Language set to {lang_name}")
        self.preview_voice()

    def change_accent(self, event):
        accent = self.accent_combobox.get()
        self.update_status(f"Accent set to {accent}")
        self.preview_voice()

    def set_language(self, language):
        self.language_combobox.set(language)
        self.change_language(None)

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
        if self.current_language == 'en':
            # Use pyttsx3 for English with Indian voices
            words = text.split()
            total_words = len(words)
            
            def update_progress(i):
                progress = (i / total_words) * 100
                self.progress['value'] = progress
                self.root.update_idletasks()
            
            for i, word in enumerate(words):
                if not self.is_speaking or self.paused:
                    break
                self.engine.say(word)
                self.engine.runAndWait()
                update_progress(i)
        else:
            # Use gTTS for Indian languages
            try:
                tts = gTTS(text=text, lang=self.current_language, slow=False)
                tts.save('temp_speech.mp3')
                os.system('start temp_speech.mp3')  # This works on Windows
                # For cross-platform, we'd need a better audio player solution
            except Exception as e:
                messagebox.showerror("Speech Error", f"Could not generate speech: {str(e)}")
        
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
                tts = gTTS(text, lang=self.current_language)
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
    
    def translate_to_hindi(self):
        """Placeholder for translation functionality"""
        text = self.text_input.get("1.0", tk.END).strip()
        if not text:
            return
            
        # In a real app, this would call a translation API
        messagebox.showinfo("Translation", 
                          "Translation service would connect to Google Translate API in the full version.\n\n" +
                          "For now, please use external translation tools and paste the result.")
    
    def save_preset(self):
        preset_name = simpledialog.askstring("Save Preset", "Enter a name for this preset:")
        if preset_name:
            preset = {
                'name': preset_name,
                'voice_index': self.current_voice,
                'rate': self.rate,
                'volume': self.volume,
                'language': self.current_language,
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
            self.current_language = preset.get('language', 'en')
            
            # Update UI controls
            self.voice_combobox.current(self.current_voice)
            self.rate_slider.set(self.rate)
            self.volume_slider.set(self.volume * 100)
            self.rate_label.config(text=f"{self.rate} wpm")
            self.volume_label.config(text=f"{int(self.volume*100)}%")
            
            # Update language selection
            lang_name = next((k for k, v in self.indian_languages.items() 
                            if v == self.current_language), 'English')
            self.language_combobox.set(lang_name)
            
            self.update_engine_settings()
            self.update_status(f"Loaded preset: {preset['name']}")
            self.preview_voice()
    
    def update_presets_dropdown(self):
        self.preset_combobox['values'] = [p['name'] for p in self.saved_presets]
        if self.saved_presets:
            self.preset_combobox.current(0)
    
    def load_presets(self):
        """Load saved presets from JSON file"""
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
                if self.current_language == 'en':
                    self.engine.say(text)
                    self.engine.runAndWait()
                else:
                    try:
                        tts = gTTS(text=text, lang=self.current_language, slow=False)
                        tts.save('temp_speech.mp3')
                        os.system('start temp_speech.mp3')
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not generate speech: {str(e)}")
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
    
    def open_english_learning(self):
        """Open English learning resources for Indian users"""
        webbrowser.open("https://learnenglish.britishcouncil.org/")

    def open_hindi_tutorial(self):
        """Open Hindi tutorial for the app"""
        webbrowser.open("https://www.youtube.com/results?search_query=Speak4Me+Pro+Hindi+Tutorial")

    def open_upi_payment(self):
        """Open UPI payment interface"""
        messagebox.showinfo("UPI Payment", 
                          "In the full version, this would integrate with UPI payment gateways like:\n\n" +
                          "- PhonePe\n- Google Pay\n- Paytm\n- BHIM\n\n" +
                          "For now, please visit our website to purchase the pro version.")

    def open_indian_support(self):
        """Open Indian customer support"""
        webbrowser.open("mailto:support@BE_MY_VOICE.in?subject=Speak4Me%20Pro%20Support")

    def open_indian_payment(self):
        """Open Indian payment options"""
        webbrowser.open("https://example.com/BE_MY_VOICE-india-purchase")

    def show_about(self):
        about_text = """Speak4Me Pro - India Edition
        
Version: 2.5
Developed for Indian Market

Features for Indian Users:
- Support for 12 Indian languages
- Indian English accents
- UPI payment integration
- Hindi tutorial videos
- Regional language support
- Optimized for Indian pronunciation
- Affordable pricing in INR

Contact: support@BE_MY_VOICE.in
Phone: +91-XXXXXXXXXX"""

        messagebox.showinfo("About Speak4Me Pro - India Edition", about_text)

    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk()
    app = BE_MY_VOICE(root)
    root.mainloop()
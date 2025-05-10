import pyttsx3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
import os
import json
from datetime import datetime
from gtts import gTTS
import pyperclip

class Speak4MePro:
    def __init__(self, root):
        self.root = root
        self.root.title("Speak4Me Pro - Advanced Text to Speech")
        self.root.geometry("900x650")
        self.root.minsize(700, 500)
        
        
        self.engine = pyttsx3.init()
        self.voices = self.engine.getProperty('voices')
        self.current_voice = 0
        self.rate = 150
        self.volume = 1.0
        self.is_speaking = False
        self.paused = False
        self.saved_presets = []
        self.dark_mode = False
        
      
        self.load_presets()
        
      
        self.setup_ui()
        
       
        for i, voice in enumerate(self.voices):
            if "female" in voice.name.lower():
                self.current_voice = i
                break
        
        
        self.update_engine_settings()

    def setup_ui(self):
       
        self.style = ttk.Style()
        self.style.configure('TButton', font=('Arial', 10))
        self.style.configure('TLabel', font=('Arial', 10))
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        
        self.setup_menu_bar()
        
       
        text_frame = ttk.LabelFrame(main_frame, text="Text to Speak", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.text_input = tk.Text(text_frame, wrap=tk.WORD, font=('Arial', 12))
        self.text_input.pack(fill=tk.BOTH, expand=True)
        
        
        scrollbar = ttk.Scrollbar(self.text_input)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_input.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.text_input.yview)
        
        
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        
        voice_frame = ttk.LabelFrame(controls_frame, text="Voice Settings", padding="10")
        voice_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        ttk.Label(voice_frame, text="Voice:").grid(row=0, column=0, sticky=tk.W)
        self.voice_combobox = ttk.Combobox(voice_frame, state="readonly")
        self.voice_combobox.grid(row=0, column=1, sticky=tk.EW, padx=5)
        self.voice_combobox['values'] = [voice.name for voice in self.voices]
        self.voice_combobox.current(self.current_voice)
        self.voice_combobox.bind("<<ComboboxSelected>>", self.change_voice)
        
         
        ttk.Label(voice_frame, text="Speed:").grid(row=1, column=0, sticky=tk.W)
        self.rate_slider = ttk.Scale(voice_frame, from_=50, to=300, value=self.rate, 
                                    command=lambda v: self.update_rate(int(float(v))))
        self.rate_slider.grid(row=1, column=1, sticky=tk.EW, padx=5)
        self.rate_label = ttk.Label(voice_frame, text=f"{self.rate} wpm")
        self.rate_label.grid(row=1, column=2, padx=5)
        
        
        ttk.Label(voice_frame, text="Volume:").grid(row=2, column=0, sticky=tk.W)
        self.volume_slider = ttk.Scale(voice_frame, from_=0, to=100, value=self.volume*100, 
                                      command=lambda v: self.update_volume(float(v)/100))
        self.volume_slider.grid(row=2, column=1, sticky=tk.EW, padx=5)
        self.volume_label = ttk.Label(voice_frame, text=f"{int(self.volume*100)}%")
        self.volume_label.grid(row=2, column=2, padx=5)
        
        
        button_frame = ttk.Frame(controls_frame, padding="10")
        button_frame.pack(side=tk.RIGHT)
        
        self.play_btn = ttk.Button(button_frame, text="Speak", command=self.toggle_speech)
        self.play_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Stop", command=self.stop_speech).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Pause", command=self.pause_speech).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Quick Speak", command=self.create_mini_mode).pack(side=tk.LEFT, padx=5)
        
        
        file_frame = ttk.Frame(main_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(file_frame, text="Open File", command=self.open_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save Text", command=self.save_text).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Export MP3", command=self.save_as_mp3).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Paste Clipboard", command=self.read_clipboard).pack(side=tk.LEFT, padx=5)
        
        
        self.preset_combobox = ttk.Combobox(file_frame, state="readonly", width=25)
        self.preset_combobox.pack(side=tk.LEFT, padx=5)
        self.update_presets_dropdown()
        ttk.Button(file_frame, text="Load Preset", command=self.load_preset).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Save Preset", command=self.save_preset).pack(side=tk.LEFT, padx=5)
        
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN).pack(fill=tk.X, pady=5)

    def setup_menu_bar(self):
        menubar = tk.Menu(self.root)
        
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_file)
        file_menu.add_command(label="Save Text", command=self.save_text)
        file_menu.add_command(label="Export as MP3", command=self.save_as_mp3)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Paste Clipboard", command=self.read_clipboard)
        edit_menu.add_command(label="Clear Text", command=self.clear_text)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        menubar.add_cascade(label="View", menu=view_menu)
        
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
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
    
    def speak_text(self, text):
        self.engine.say(text)
        self.engine.runAndWait()
        if not self.paused:
            self.is_speaking = False
            self.play_btn.config(text="Speak")
            self.update_status("Finished speaking")
    
    def preview_voice(self):
        if self.is_speaking:
            return
        threading.Thread(
            target=lambda: self.engine.say("This is how I sound now"),
            daemon=True
        ).start()
    
    def open_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Text Files", ".txt"), ("All Files", ".*")]
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
            filetypes=[("Text Files", ".txt"), ("All Files", ".*")]
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
    
    def save_preset(self):
        preset_name = simpledialog.askstring("Save Preset", "Enter a name for this preset:")
        if preset_name:
            preset = {
                'name': preset_name,
                'voice_index': self.current_voice,
                'rate': self.rate,
                'volume': self.volume,
                'timestamp': datetime.now().isoformat()
            }
            
            
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
            
            
            self.voice_combobox.current(self.current_voice)
            self.rate_slider.set(self.rate)
            self.volume_slider.set(self.volume * 100)
            self.rate_label.config(text=f"{self.rate} wpm")
            self.volume_label.config(text=f"{int(self.volume*100)}%")
            
            self.update_engine_settings()
            self.update_status(f"Loaded preset: {preset['name']}")
            self.preview_voice()
    
    def update_presets_dropdown(self):
        self.preset_combobox['values'] = [p['name'] for p in self.saved_presets]
        if self.saved_presets:
            self.preset_combobox.current(0)
    
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
    
    def create_mini_mode(self):
        mini_win = tk.Toplevel(self.root)
        mini_win.title("Speak4Me Quick")
        mini_win.geometry("300x150")
        
        ttk.Label(mini_win, text="Enter text to speak:").pack(pady=5)
        
        entry = ttk.Entry(mini_win, width=30)
        entry.pack(pady=5)
        entry.focus()
        
        def speak_and_close():
            text = entry.get()
            if text:
                self.engine.say(text)
                self.engine.runAndWait()
            mini_win.destroy()
        
        btn_frame = ttk.Frame(mini_win)
        btn_frame.pack(pady=5)
        
        ttk.Button(btn_frame, text="Speak", command=speak_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=mini_win.destroy).pack(side=tk.LEFT, padx=5)
    
    def toggle_dark_mode(self):
        if self.dark_mode:
            self.root.configure(bg='SystemButtonFace')
            self.style.theme_use('clam')
            self.dark_mode = False
            self.update_status("Light mode activated")
        else:
            self.root.configure(bg='#2d2d2d')
            self.style.theme_use('alt')
            self.dark_mode = True
            self.update_status("Dark mode activated")
    
    def show_about(self):
        about_text = """Speak4Me Pro - Advanced Text to Speech
        
Version: 2.0
Developed for Hackathon Project

Features:
- Multiple voice support
- Adjustable speed and volume
- Save/Load presets
- Export to MP3
- Quick speak mode
- Dark/Light theme"""
        
        messagebox.showinfo("About Speak4Me Pro", about_text)
    
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()

if __name__ == "__main__":
    root = tk.Tk()
    app = Speak4MePro(root)
    root.mainloop()
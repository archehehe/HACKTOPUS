import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import folium
import webbrowser
import os
import json
import random
import math
import requests
import sqlite3
from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from folium.plugins import MarkerCluster, MousePosition, MeasureControl
import sv_ttk
from PIL import Image, ImageTk
import io
import threading
import pyttsx3
import base64
import geocoder
import numpy as np
import aiohttp
import asyncio
from concurrent.futures import ThreadPoolExecutor
from tenacity import retry, stop_after_attempt, wait_fixed

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("Warning: reportlab not installed. PDF report generation will be disabled.")

class WheelMatePro:
    def __init__(self, root):
        self.root = root
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.db_conn = None
        self.google_api_key = "AIzaSyDZHYD7fUxTiPNQMfHlxqOkWskwYX_hciQ"  # Provided API key
        self._configure_main_window()
        self._initialize_services()
        self._setup_database()
        self._load_data()
        self._setup_ui()
        self._show_splash_screen()
        self._show_welcome_message()
        self.search_location("AMC Engineering College, Bangalore, Karnataka")  # Default search

    def _configure_main_window(self):
        self.root.title("WheelMate Pro ♿ - Accessibility Navigator")
        self.root.geometry("1400x850")
        self.root.minsize(1200, 750)
        try:
            self.root.iconbitmap("wheelmate_icon.ico")
        except:
            pass

    def _initialize_services(self):
        self.geolocator = Nominatim(user_agent="wheelmate_pro", timeout=5)
        self.geocode = RateLimiter(self.geolocator.geocode, min_delay_seconds=0.5)
        self.tts_engine = pyttsx3.init()
        self.locations = []
        self.current_location = None
        self.search_radius = 5
        self.map_file = "wheelmate_map.html"
        self.nearby_places = []
        self.user_profile = {
            'mobility_type': 'manual_wheelchair',
            'max_slope': 8.0,
            'min_door_width': 80,
            'preferred_surface': 'smooth',
            'username': 'Guest',
            'profile_picture': None
        }
        self.user_prefs = {
            'theme': 'light',
            'default_radius': 5,
            'recent_searches': [],
            'high_contrast': False,
            'voice_enabled': False,
            'offline_mode': False
        }
        self.load_preferences()
        self.demo_mode = False
        self.offline_cache = {}
        self.db_lock = threading.Lock()
        self.update_pending = False

    def _setup_database(self):
        self.db_conn = sqlite3.connect('wheelmate_cache.db', check_same_thread=False)
        c = self.db_conn.cursor()
        expected_columns = [
            'name TEXT', 'lat REAL', 'lon REAL', 'rating INTEGER', 'type TEXT',
            'description TEXT', 'features TEXT', 'last_updated TEXT',
            'slope REAL', 'door_width INTEGER', 'surface TEXT', 'photo BLOB',
            'address TEXT'  # Added address column
        ]
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='places'")
        if c.fetchone():
            c.execute("PRAGMA table_info(places)")
            columns = [col[1] for col in c.fetchall()]
            expected_names = [col.split()[0] for col in expected_columns]
            if columns != expected_names:
                c.execute("DROP TABLE places")
                c.execute(f"CREATE TABLE places ({', '.join(expected_columns)})")
        else:
            c.execute(f"CREATE TABLE places ({', '.join(expected_columns)})")
        c.execute("CREATE INDEX IF NOT EXISTS idx_places_lat_lon ON places(lat, lon)")
        c.execute('''CREATE TABLE IF NOT EXISTS verifications 
                     (place_name TEXT, user TEXT, verified INTEGER, timestamp TEXT)''')
        self.db_conn.commit()

    def _load_data(self):
        try:
            with open('wheelmate_offline.json', 'r') as f:
                self.offline_cache = json.load(f)
                self.nearby_places = self.offline_cache.get('places', [])
                self.current_location = self.offline_cache.get('location', None)
        except FileNotFoundError:
            pass

    def _setup_ui(self):
        sv_ttk.set_theme(self.user_prefs['theme'])
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.left_frame = ttk.Frame(self.main_frame, width=500)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=5, pady=5)
        self.right_frame = ttk.Frame(self.main_frame)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self._build_header()
        self._build_search_controls()
        self._build_filter_panel()
        self._build_profile_panel()
        self._build_rating_controls()
        self._build_stats_panel()
        self._build_map_panel()
        self._build_location_list()
        self._build_status_bar()
        self._add_visual_effects()

    def _build_header(self):
        header_frame = ttk.Frame(self.left_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Label(header_frame, text="♿ WheelMate Pro", 
                 font=('Arial', 20, 'bold'), foreground='#2a4a7f').pack(side=tk.LEFT)
        ttk.Button(header_frame, text="🌙 Theme", command=self.toggle_theme,
                  width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="🎤 Voice", command=self.toggle_voice,
                  width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(header_frame, text="ℹ️ Help", command=self.show_help,
                  width=8).pack(side=tk.RIGHT)

    def _build_search_controls(self):
        search_frame = ttk.LabelFrame(self.left_frame, text="🔍 Search Location", padding=15)
        search_frame.pack(fill=tk.X, pady=5)
        self.search_entry = ttk.Entry(search_frame, font=('Arial', 11))
        self.search_entry.pack(fill=tk.X, pady=5)
        self.search_entry.bind("<Return>", lambda e: self.search_location())
        self.search_entry.configure(takefocus=True)
        self.search_entry.focus_set()
        btn_frame = ttk.Frame(search_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Search", command=self.search_location).pack(side=tk.LEFT, expand=True)
        ttk.Button(btn_frame, text="My Location", command=self.use_current_location).pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(btn_frame, text="Random City", command=self.random_city).pack(side=tk.LEFT, expand=True)
        ttk.Button(btn_frame, text="Demo Mode", command=self.toggle_demo_mode).pack(side=tk.LEFT, expand=True, padx=5)
        radius_frame = ttk.Frame(search_frame)
        radius_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Label(radius_frame, text="Search Radius:").pack(side=tk.LEFT)
        self.radius_slider = ttk.Scale(radius_frame, from_=1, to=20, value=self.search_radius,
                                     command=lambda v: self.update_radius(float(v)))
        self.radius_slider.pack(side=tk.LEFT, expand=True, padx=5)
        self.radius_label = ttk.Label(radius_frame, text=f"{self.search_radius:.1f} km")
        self.radius_label.pack(side=tk.LEFT)

    def _build_filter_panel(self):
        filter_frame = ttk.LabelFrame(self.left_frame, text="⚙️ Accessibility Filters", padding=10)
        filter_frame.pack(fill=tk.X, pady=5)
        self.filters = {
            'ramp': tk.BooleanVar(value=True),
            'restroom': tk.BooleanVar(value=True),
            'elevator': tk.BooleanVar(value=False),
            'wide_door': tk.BooleanVar(value=False),
            'smooth_surface': tk.BooleanVar(value=False),
            'low_slope': tk.BooleanVar(value=False)
        }
        for key, var in self.filters.items():
            ttk.Checkbutton(filter_frame, text=key.replace('_', ' ').title(), 
                           variable=var, command=self.apply_filters).pack(anchor=tk.W)
        slope_frame = ttk.Frame(filter_frame)
        slope_frame.pack(fill=tk.X, pady=5)
        ttk.Label(slope_frame, text="Max Slope (°):").pack(side=tk.LEFT)
        self.slope_entry = ttk.Entry(slope_frame, width=10)
        self.slope_entry.insert(0, str(self.user_profile['max_slope']))
        self.slope_entry.pack(side=tk.LEFT, padx=5)
        door_frame = ttk.Frame(filter_frame)
        door_frame.pack(fill=tk.X, pady=5)
        ttk.Label(door_frame, text="Min Door Width (cm):").pack(side=tk.LEFT)
        self.door_width_entry = ttk.Entry(door_frame, width=10)
        self.door_width_entry.insert(0, str(self.user_profile['min_door_width']))
        self.door_width_entry.pack(side=tk.LEFT, padx=5)

    def _build_profile_panel(self):
        profile_frame = ttk.LabelFrame(self.left_frame, text="👤 User Profile", padding=10)
        profile_frame.pack(fill=tk.X, pady=5)
        ttk.Label(profile_frame, text=f"User: {self.user_profile['username']}").pack(anchor=tk.W)
        ttk.Label(profile_frame, text="Mobility Type:").pack(anchor=tk.W)
        self.mobility_combo = ttk.Combobox(profile_frame, 
                                         values=['Manual Wheelchair', 'Powered Wheelchair', 'Walker'],
                                         state='readonly')
        self.mobility_combo.set(self.user_profile['mobility_type'].title())
        self.mobility_combo.pack(fill=tk.X, pady=5)
        self.mobility_combo.bind("<<ComboboxSelected>>", self.update_profile)
        ttk.Button(profile_frame, text="Edit Profile", command=self.edit_profile).pack(fill=tk.X, pady=5)
        ttk.Button(profile_frame, text="Upload Profile Picture", command=self.upload_profile_picture).pack(fill=tk.X, pady=5)

    def _build_rating_controls(self):
        rating_frame = ttk.LabelFrame(self.left_frame, text="⭐ Rate & Audit Accessibility", padding=15)
        rating_frame.pack(fill=tk.X, pady=5)
        self.rating_var = tk.StringVar(value="3")
        rating_btn_frame = ttk.Frame(rating_frame)
        rating_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(rating_btn_frame, text="🟢 Fully", command=lambda: self.rating_var.set("3"),
                  style='Accent.TButton' if self.rating_var.get() == "3" else 'TButton').pack(side=tk.LEFT, expand=True)
        ttk.Button(rating_btn_frame, text="🟡 Partial", command=lambda: self.rating_var.set("2"),
                  style='Accent.TButton' if self.rating_var.get() == "2" else 'TButton').pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(rating_btn_frame, text="🔴 Limited", command=lambda: self.rating_var.set("1"),
                  style='Accent.TButton' if self.rating_var.get() == "1" else 'TButton').pack(side=tk.LEFT, expand=True)
        ttk.Button(rating_btn_frame, text="⚪ Unknown", command=lambda: self.rating_var.set("0"),
                  style='Accent.TButton' if self.rating_var.get() == "0" else 'TButton').pack(side=tk.LEFT, expand=True, padx=5)
        ttk.Button(rating_frame, text="➕ Add Rating", 
                  command=self.add_rating, style='Accent.TButton').pack(fill=tk.X, pady=5)
        ttk.Button(rating_frame, text="📸 Upload Photo", 
                  command=self.upload_place_photo, style='Accent.TButton').pack(fill=tk.X, pady=5)
        ttk.Button(rating_frame, text="✅ Verify Place", 
                  command=self.verify_place, style='Accent.TButton').pack(fill=tk.X, pady=5)
        ttk.Button(rating_frame, text="📤 Share Rating", 
                  command=self.share_rating, style='Accent.TButton').pack(fill=tk.X, pady=5)
        ttk.Button(rating_frame, text="📄 Generate Audit Report", 
                  command=self.generate_audit_report, style='Accent.TButton').pack(fill=tk.X, pady=5)

    def _build_stats_panel(self):
        self.stats_frame = ttk.LabelFrame(self.left_frame, text="📊 Area Statistics", padding=15)
        self.stats_frame.pack(fill=tk.X, pady=5)
        self.stats_label = ttk.Label(self.stats_frame, text="Search a location to see statistics", 
                                   justify=tk.LEFT)
        self.stats_label.pack(fill=tk.X)
        self.progress_bars = {}
        for rating in [3, 2, 1, 0]:
            frame = ttk.Frame(self.stats_frame)
            frame.pack(fill=tk.X, pady=2)
            ttk.Label(frame, text=self._rating_text(rating), width=15, anchor=tk.W).pack(side=tk.LEFT)
            self.progress_bars[rating] = ttk.Progressbar(frame, orient=tk.HORIZONTAL, 
                                                       length=150, mode='determinate',
                                                       style=f'{self._rating_color(rating)}.Horizontal.TProgressbar')
            self.progress_bars[rating].pack(side=tk.LEFT, expand=True, padx=5)

    def _build_map_panel(self):
        map_frame = ttk.LabelFrame(self.right_frame, text="🗺️ Interactive Accessibility Map", padding=10)
        map_frame.pack(fill=tk.BOTH, expand=True)
        key_frame = ttk.Frame(map_frame)
        key_frame.pack(fill=tk.X, pady=5)
        for rating in [3, 2, 1, 0]:
            ttk.Label(key_frame, text=self._rating_text(rating), 
                     foreground='black', background=self._rating_color(rating, light=True),
                     padding=3, relief=tk.RIDGE).pack(side=tk.LEFT, padx=2)
        map_controls = ttk.Frame(map_frame)
        map_controls.pack(fill=tk.X, pady=5)
        ttk.Button(map_controls, text="Open in Browser", command=self.open_map_in_browser).pack(side=tk.LEFT)
        ttk.Button(map_controls, text="Refresh Map", command=self._update_map).pack(side=tk.LEFT, padx=5)
        ttk.Button(map_controls, text="Zoom In", command=self.zoom_in_area).pack(side=tk.LEFT)
        ttk.Button(map_controls, text="Zoom Out", command=self.zoom_out_area).pack(side=tk.LEFT, padx=5)
        ttk.Button(map_controls, text="Find Nearest", command=self.find_nearest_accessible).pack(side=tk.LEFT)
        ttk.Button(map_controls, text="Plan Route", command=self.plan_accessible_route).pack(side=tk.LEFT, padx=5)
        ttk.Button(map_controls, text="Cache Map", command=self.cache_map_offline).pack(side=tk.LEFT, padx=5)

    def _build_location_list(self):
        list_frame = ttk.LabelFrame(self.right_frame, text="📍 Nearby Accessible Locations", padding=10)
        list_frame.pack(fill=tk.BOTH, pady=5, expand=True)
        self.location_tree = ttk.Treeview(list_frame, columns=("name", "distance", "rating", "type", "verified"), 
                                        show="headings", height=12)
        self.location_tree.heading("name", text="Name", anchor=tk.W)
        self.location_tree.heading("distance", text="Distance", anchor=tk.W)
        self.location_tree.heading("rating", text="Accessibility", anchor=tk.W)
        self.location_tree.heading("type", text="Type", anchor=tk.W)
        self.location_tree.heading("verified", text="Verified", anchor=tk.W)
        self.location_tree.column("name", width=250, anchor=tk.W)
        self.location_tree.column("distance", width=100, anchor=tk.W)
        self.location_tree.column("rating", width=120, anchor=tk.W)
        self.location_tree.column("type", width=120, anchor=tk.W)
        self.location_tree.column("verified", width=80, anchor=tk.W)
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.location_tree.yview)
        self.location_tree.configure(yscrollcommand=vsb.set)
        self.location_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.location_tree.bind("<<TreeviewSelect>>", self.on_location_select)
        self.location_tree.bind("<Double-1>", self.on_location_double_click)

    def _build_status_bar(self):
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Search for a location to begin")
        ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, 
                 anchor=tk.W, padding=5).pack(fill=tk.X, side=tk.BOTTOM)

    def _add_visual_effects(self):
        self.location_tree.tag_configure('hover', background='#e6f3ff')
        self.location_tree.tag_configure('verified', foreground='green')
        self.location_tree.bind('<Motion>', self.on_tree_hover)
        for rating in range(4):
            self.location_tree.tag_configure(f"rating_{rating}", 
                                          background=self._rating_color(rating, light=True))

    def _rating_text(self, rating):
        return {3: "Fully Accessible", 2: "Partially Accessible", 
                1: "Limited Accessibility", 0: "Unknown"}.get(rating, "Unknown")

    def _rating_color(self, rating, light=False):
        colors = {3: ("#4CAF50", "#C8E6C9"), 2: ("#FFC107", "#FFECB3"), 
                  1: ("#F44336", "#FFCDD2"), 0: ("#757575", "#E0E0E0")}
        return colors.get(rating, ("#757575", "#E0E0E0"))[1 if light else 0]

    def _calculate_distances(self, loc1, locations):
        R = 6371  # Earth's radius in km
        lat1, lon1 = loc1
        lat2 = np.array([loc['lat'] for loc in locations])
        lon2 = np.array([loc['lon'] for loc in locations])
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        return R * c

    async def _fetch_google_places(self, lat, lon, radius_km):
        places = []
        url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
        params = {
            "location": f"{lat},{lon}",
            "radius": radius_km * 1000,
            "key": self.google_api_key,
            "type": "point_of_interest|restaurant|cafe|shop|park|library|bank|pharmacy"
        }
        async with aiohttp.ClientSession() as session:
            while url:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        print(f"Google API error: {response.status}")
                        break
                    data = await response.json()
                    for place in data.get("results", []):
                        place_id = place.get("place_id")
                        details = await self._fetch_place_details(place_id, session)
                        accessibility_rating = self._determine_accessibility(details, place.get("types", []))
                        places.append({
                            'name': place.get("name", "Unnamed Place"),
                            'type': place.get("types", ["point_of_interest"])[0].replace("_", " "),
                            'lat': place.get("geometry", {}).get("location", {}).get("lat"),
                            'lon': place.get("geometry", {}).get("location", {}).get("lng"),
                            'rating': accessibility_rating,
                            'address': details.get("formatted_address", "Unknown"),
                            'description': self._rating_text(accessibility_rating),
                            'features': details.get("wheelchair_accessible_entrance", False) and "Wheelchair ramp, wide doorways" or "No accessibility features",
                            'last_updated': datetime.now().strftime('%Y-%m-%d'),
                            'slope': None,
                            'door_width': None,
                            'surface': "unknown",
                            'photo': None
                        })
                    next_page_token = data.get("next_page_token")
                    url = next_page_token and f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?pagetoken={next_page_token}&key={self.google_api_key}" or None
                    await asyncio.sleep(2)  # Respect API rate limits
        return places[:50]  # Limit to 50 places

    async def _fetch_place_details(self, place_id, session):
        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": place_id,
            "fields": "formatted_address,wheelchair_accessible_entrance",
            "key": self.google_api_key
        }
        async with session.get(url, params=params) as response:
            if response.status == 200:
                return (await response.json()).get("result", {})
        return {}

    def _determine_accessibility(self, details, place_types):
        modern_types = ["restaurant", "cafe", "shopping_mall", "library", "bank", "pharmacy"]
        if details.get("wheelchair_accessible_entrance", False):
            return random.choices([3, 2], weights=[70 if any(t in place_types for t in modern_types) else 50, 30])[0]
        return random.choices([1, 0], weights=[80, 20])[0]

    def _fetch_cached_places(self, lat, lon):
        places = []
        with self.db_lock:
            c = self.db_conn.cursor()
            c.execute("SELECT * FROM places WHERE lat > ? AND lat < ? AND lon > ? AND lon < ?",
                     (lat - 0.1, lat + 0.1, lon - 0.1, lon + 0.1))
            for row in c.fetchall():
                places.append({
                    'name': row[0], 'lat': row[1], 'lon': row[2], 'rating': row[3],
                    'type': row[4], 'description': row[5], 'features': row[6],
                    'last_updated': row[7], 'slope': row[8], 'door_width': row[9],
                    'surface': row[10], 'photo': row[11], 'address': row[12]
                })
        return places

    def _fetch_real_places(self, lat, lon):
        if self.user_prefs.get('offline_mode', False):
            return self._fetch_cached_places(lat, lon)

        async def fetch_all():
            places = []
            google_task = self._fetch_google_places(lat, lon, self.search_radius)
            google_data = await google_task
            places.extend(google_data)
            return places

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            places = loop.run_until_complete(fetch_all())
        finally:
            loop.close()

        if self.demo_mode and not places:
            places.extend(self._generate_nearby_places(lat, lon))

        return places[:150]

    def _cache_places(self, places):
        with self.db_lock:
            c = self.db_conn.cursor()
            c.execute("DELETE FROM places")
            data = [
                (p['name'], p['lat'], p['lon'], p['rating'], p['type'], p['description'],
                 p['features'], p['last_updated'], p['slope'], p['door_width'],
                 p['surface'], p['photo'], p['address'])
                for p in places
            ]
            c.executemany("INSERT INTO places VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", data)
            self.db_conn.commit()
        try:
            with open('nearby_places.json', 'w') as f:
                json.dump(places, f, indent=4)
        except Exception as e:
            print(f"Failed to save to JSON: {str(e)}")

    def toggle_theme(self):
        self.user_prefs['theme'] = 'dark' if self.user_prefs['theme'] == 'light' else 'light'
        sv_ttk.set_theme(self.user_prefs['theme'])
        self.save_preferences()
        self.update_status(f"Switched to {self.user_prefs['theme'].capitalize()} Mode")
        if self.user_prefs['voice_enabled']:
            self.read_status(f"Switched to {self.user_prefs['theme'].capitalize()} Mode")

    def toggle_voice(self):
        self.user_prefs['voice_enabled'] = not self.user_prefs['voice_enabled']
        self.save_preferences()
        self.update_status(f"Voice navigation {'enabled' if self.user_prefs['voice_enabled'] else 'disabled'}")
        if self.user_prefs['voice_enabled']:
            self.read_status("Voice navigation enabled")

    def toggle_demo_mode(self):
        self.demo_mode = not self.demo_mode
        self.update_status(f"Demo mode {'enabled' if self.demo_mode else 'disabled'}")
        if self.demo_mode:
            self.search_location("Eiffel Tower, Paris")
            self.read_status("Demo mode enabled. Showing sample data for Paris.")

    def update_radius(self, radius):
        self.search_radius = radius
        self.radius_label.config(text=f"{radius:.1f} km")
        if self.current_location:
            self.schedule_update_display()

    def zoom_in_area(self):
        self.search_radius = max(1, self.search_radius * 0.7)
        self.radius_slider.set(self.search_radius)
        self.update_status(f"Zoomed in to {self.search_radius:.1f} km radius")
        self.schedule_update_display()

    def zoom_out_area(self):
        self.search_radius = min(20, self.search_radius * 1.3)
        self.radius_slider.set(self.search_radius)
        self.update_status(f"Zoomed out to {self.search_radius:.1f} km radius")
        self.schedule_update_display()

    def _show_splash_screen(self):
        splash = tk.Toplevel(self.root)
        splash.geometry("400x300")
        splash.overrideredirect(True)
        ttk.Label(splash, text="WheelMate Pro\nEmpowering Accessible Travel", 
                 font=('Arial', 16, 'bold'), justify=tk.CENTER).pack(pady=50)
        ttk.Label(splash, text="Loading...", font=('Arial', 12)).pack()
        self.root.after(1000, splash.destroy)

    def _show_welcome_message(self):
        welcome_msg = """Welcome to WheelMate Pro!
Key Features:
• Real-time accessibility data
• Enhanced filters
• Wheelchair-friendly routes
• User profiles
• Community contributions
• Offline caching
• Audit reports"""
        messagebox.showinfo("Welcome", welcome_msg.strip())
        if self.user_prefs['voice_enabled']:
            self.read_status(welcome_msg)

    def show_help(self):
        help_text = """WheelMate Pro Help:
🔍 Search: Enter address or use GPS
⚙️ Filters: Select accessibility needs
👤 Profile: Customize settings
⭐ Rate: Add ratings/photos
🗺️ Map: Plan routes, cache offline
📊 Stats: View accessibility data"""
        messagebox.showinfo("Help Guide", help_text.strip())
        if self.user_prefs['voice_enabled']:
            self.read_status(help_text)

    def use_current_location(self):
        if self.demo_mode:
            self.search_location("Times Square, New York")
            return
        try:
            g = geocoder.ip('me')
            if g.ok:
                self.current_location = (g.lat, g.lng)
                location = self.geolocator.reverse((g.lat, g.lng), language='en')
                address = location.address if location else f"{g.lat:.4f}, {g.lng:.4f}"
                self.search_entry.delete(0, tk.END)
                self.search_entry.insert(0, address)
                self.search_location(address)
                self.update_status("Using your current location")
                if self.user_prefs['voice_enabled']:
                    self.read_status(f"Using your current location: {address}")
            else:
                raise Exception("Geolocation failed")
        except Exception as e:
            messagebox.showinfo("Current Location", 
                              f"Could not get GPS: {str(e)}\nUsing AMC Engineering College.")
            self.search_location("AMC Engineering College, Bangalore, Karnataka")

    def search_location(self, query=None):
        query = query or self.search_entry.get()
        if not query:
            messagebox.showwarning("Warning", "Please enter a location")
            return
        self.update_status("Searching location...")
        self.executor.submit(self._perform_search, query)

    async def _fetch_osm_data(self, session, lat, lon):
        overpass_url = "http://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:5];
        node["wheelchair"](around:{min(self.search_radius*1000, 5000)},{lat},{lon});
        out body 100;
        """
        try:
            async with session.get(overpass_url, params={'data': query}, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['elements']
                return []
        except:
            return []

    async def _fetch_wheelmap_data(self, session, lat, lon):
        wheelmap_url = f"https://wheelmap.org/api/nodes?bbox={lon-0.05},{lat-0.05},{lon+0.05},{lat+0.05}&api_key=YOUR_WHEELMAP_API_KEY"
        try:
            async with session.get(wheelmap_url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['nodes']
                return []
        except:
            return []

    def _perform_search(self, query):
        try:
            location = self.geocode(query)
            if not location:
                raise Exception("Location not found")
            self.current_location = (location.latitude, location.longitude)
            self.root.after(0, lambda: self.search_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.search_entry.insert(0, location.address))
            if query not in self.user_prefs['recent_searches']:
                self.user_prefs['recent_searches'].insert(0, query)
                self.user_prefs['recent_searches'] = self.user_prefs['recent_searches'][:5]
                self.save_preferences()
            cached_places = self._fetch_cached_places(location.latitude, location.longitude)
            if cached_places and self._is_cache_valid(location.latitude, location.longitude):
                self.actuallat = location.latitude
                self.actuallon = location.longitude
                self.nearby_places = cached_places
            else:
                self.nearby_places = self._fetch_real_places(location.latitude, location.longitude)
                self._cache_places(self.nearby_places)
            self.root.after(0, self.schedule_update_display)
            self.root.after(0, lambda: self.update_status(f"Showing {len(self.nearby_places)} places near {location.address}"))
            if self.user_prefs['voice_enabled']:
                self.root.after(0, lambda: self.read_status(f"Found {len(self.nearby_places)} places near {location.address}"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Search failed: {str(e)}"))
            self.root.after(0, lambda: self.update_status("Search failed"))

    def _is_cache_valid(self, lat, lon):
        c = self.db_conn.cursor()
        c.execute("SELECT last_updated FROM places LIMIT 1")
        result = c.fetchone()
        if not result:
            return False
        last_updated = datetime.strptime(result[0], '%Y-%m-%d')
        return (datetime.now() - last_updated).days < 7

    def _generate_nearby_places(self, lat, lon):
        place_types = [
            ('restaurant', 0.3, ['Ramp entrance', 'Accessible restrooms'], 5.0, 90, 'smooth'),
            ('cafe', 0.2, ['Step-free entry', 'Lowered counter'], 3.0, 85, 'paved'),
            ('museum', 0.15, ['Elevators', 'Wheelchair loans'], 6.0, 100, 'smooth'),
            ('park', 0.1, ['Paved pathways', 'Accessible parking'], 2.0, None, 'paved'),
            ('hotel', 0.08, ['Accessible rooms', 'Roll-in showers'], 4.0, 95, 'smooth')
        ]
        places = []
        for category, weight, features, slope, door_width, surface in place_types:
            for _ in range(max(1, int(5 * weight))):
                dist = random.uniform(0, self.search_radius) * random.uniform(0, 1)
                angle = random.uniform(0, 2 * math.pi)
                offset_lat = lat + (dist/110) * math.cos(angle)
                offset_lon = lon + (dist/110) * math.sin(angle)
                rating = random.choices([0, 1, 2, 3], weights=[1, 2, 3, 4])[0]
                place_name = f"{random.choice(['City', 'Central', 'Main'])} {category.capitalize()}"
                places.append({
                    'name': place_name,
                    'type': category,
                    'lat': offset_lat,
                    'lon': offset_lon,
                    'rating': rating,
                    'address': f"{random.randint(1, 200)} Main St",
                    'description': f"Features: {random.choice(features)}",
                    'features': random.choice(features),
                    'last_updated': datetime.now().strftime('%Y-%m-%d'),
                    'slope': slope,
                    'door_width': door_width,
                    'surface': surface,
                    'photo': None
                })
        return places

    def apply_filters(self):
        if not self.nearby_places:
            return
        try:
            max_slope = float(self.slope_entry.get())
            min_door_width = int(self.door_width_entry.get())
        except ValueError:
            messagebox.showwarning("Warning", "Please enter valid slope and door width values")
            return
        filtered_places = []
        for place in self.nearby_places:
            desc = place['description'].lower()
            matches = True
            if self.filters['ramp'].get() and 'ramp' not in desc:
                matches = False
            if self.filters['restroom'].get() and 'restroom' not in desc:
                matches = False
            if self.filters['elevator'].get() and 'elevator' not in desc:
                matches = False
            if self.filters['wide_door'].get() and 'wide door' not in desc:
                matches = False
            if self.filters['smooth_surface'].get() and place['surface'] not in ['smooth', 'paved']:
                matches = False
            if self.filters['low_slope'].get() and (place['slope'] is None or place['slope'] > max_slope):
                matches = False
            if place['slope'] is not None and place['slope'] > self.user_profile['max_slope']:
                matches = False
            if place['door_width'] is not None and place['door_width'] < self.user_profile['min_door_width']:
                matches = False
            if place['surface'] != 'unknown' and place['surface'] != self.user_profile['preferred_surface']:
                matches = False
            if matches:
                filtered_places.append(place)
        self.nearby_places = filtered_places
        self.schedule_update_display()
        self.update_status(f"Filtered to {len(filtered_places)} places")
        if self.user_prefs['voice_enabled']:
            self.read_status(f"Filtered to {len(filtered_places)} places")

    def edit_profile(self):
        username = simpledialog.askstring("Edit Profile", "Enter username:", 
                                        initialvalue=self.user_profile['username'])
        if username:
            self.user_profile['username'] = username
        max_slope = simpledialog.askfloat("Edit Profile", "Max slope (degrees):",
                                        initialvalue=self.user_profile['max_slope'])
        if max_slope is not None:
            self.user_profile['max_slope'] = max_slope
            self.slope_entry.delete(0, tk.END)
            self.slope_entry.insert(0, str(max_slope))
        min_door_width = simpledialog.askinteger("Edit Profile", "Min door width (cm):",
                                               initialvalue=self.user_profile['min_door_width'])
        if min_door_width is not None:
            self.user_profile['min_door_width'] = min_door_width
            self.door_width_entry.delete(0, tk.END)
            self.door_width_entry.insert(0, str(min_door_width))
        surface = simpledialog.askstring("Edit Profile", "Preferred surface (smooth/paved/cobblestone):",
                                       initialvalue=self.user_profile['preferred_surface'])
        if surface in ['smooth', 'paved', 'cobblestone']:
            self.user_profile['preferred_surface'] = surface
        self.save_profile()
        self.update_status(f"Profile updated for {self.user_profile['username']}")
        if self.user_prefs['voice_enabled']:
            self.read_status(f"Profile updated for {self.user_profile['username']}")

    def update_profile(self, event=None):
        mobility = self.mobility_combo.get().lower().replace(' ', '_')
        self.user_profile['mobility_type'] = mobility
        self.save_profile()
        self.update_status(f"Mobility type set to {mobility.replace('_', ' ').title()}")
        if self.user_prefs['voice_enabled']:
            self.read_status(f"Mobility type set to {mobility.replace('_', ' ').title()}")

    def upload_profile_picture(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    self.user_profile['profile_picture'] = base64.b64encode(f.read()).decode('utf-8')
                self.save_profile()
                self.update_status("Profile picture uploaded")
                if self.user_prefs['voice_enabled']:
                    self.read_status("Profile picture uploaded")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload picture: {str(e)}")

    def upload_place_photo(self):
        selected = self.location_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Please select a place to upload a photo for")
            return
        item = self.location_tree.item(selected)
        place_name = item['values'][0]
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    photo_data = base64.b64encode(f.read()).decode('utf-8')
                for place in self.nearby_places:
                    if place['name'] == place_name:
                        place['photo'] = photo_data
                        self._cache_places(self.nearby_places)
                        self.update_status(f"Photo uploaded for {place_name}")
                        if self.user_prefs['voice_enabled']:
                            self.read_status(f"Photo uploaded for {place_name}")
                        break
            except Exception as e:
                messagebox.showerror("Error", f"Failed to upload photo: {str(e)}")

    def verify_place(self):
        selected = self.location_tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Please select a place to verify")
            return
        item = self.location_tree.item(selected)
        place_name = item['values'][0]
        if messagebox.askyesno("Verify Place", f"Confirm accessibility data for {place_name}?"):
            with self.db_lock:
                c = self.db_conn.cursor()
                c.execute("INSERT INTO verifications VALUES (?, ?, ?, ?)",
                         (place_name, self.user_profile['username'], 1, datetime.now().strftime('%Y-%m-%d %H:%M')))
                self.db_conn.commit()
            self.schedule_update_display()
            self.update_status(f"Verified {place_name}")
            if self.user_prefs['voice_enabled']:
                self.read_status(f"Verified {place_name}")

    def random_city(self):
        cities = [
            "Brandenburg Gate, Berlin",
            "Eiffel Tower, Paris",
            "Colosseum, Rome",
            "Times Square, New York",
            "Sydney Opera House"
        ]
        city = random.choice(cities)
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, city)
        self.search_location(city)

    def add_rating(self):
        if not self.current_location:
            messagebox.showwarning("Warning", "Please search for a location first")
            return
        name = simpledialog.askstring("Add Rating", "Enter place name:", 
                                    initialvalue=self.search_entry.get())
        if not name:
            return
        place_type = simpledialog.askstring("Place Type", 
                                          "Enter type (e.g., restaurant, museum):",
                                          initialvalue="restaurant")
        details = simpledialog.askstring("Accessibility Details", 
                                       "Describe features (e.g., ramps, restrooms):")
        slope = simpledialog.askfloat("Slope", "Enter slope (degrees, optional):", minvalue=0)
        door_width = simpledialog.askinteger("Door Width", "Enter door width (cm, optional):", minvalue=0)
        surface = simpledialog.askstring("Surface", "Enter surface (smooth/paved/cobblestone):")
        rating = int(self.rating_var.get())
        new_place = {
            'name': name,
            'type': place_type.lower() if place_type else 'other',
            'lat': self.current_location[0] + random.uniform(-0.01, 0.01),
            'lon': self.current_location[1] + random.uniform(-0.01, 0.01),
            'rating': rating,
            'address': f"Near {self.search_entry.get()}",
            'description': details if details else "No details provided",
            'features': details,
            'last_updated': datetime.now().strftime('%Y-%m-%d'),
            'slope': slope,
            'door_width': door_width,
            'surface': surface if surface in ['smooth', 'paved', 'cobblestone', 'unknown'] else 'unknown',
            'photo': None
        }
        self.locations.append(new_place)
        self.nearby_places.append(new_place)
        self._cache_places(self.nearby_places)
        self.schedule_update_display()
        self.update_status(f"Added {self._rating_text(rating)} rating for {name}")
        if self.user_prefs['voice_enabled']:
            self.read_status(f"Added {self._rating_text(rating)} rating for {name}")

    def share_rating(self):
        if not self.nearby_places:
            messagebox.showwarning("Warning", "No ratings to share")
            return
        place = self.nearby_places[-1]
        tweet = f"Rated {place['name']} as {self._rating_text(place['rating'])} for accessibility! #WheelMatePro #Accessibility"
        webbrowser.open(f"https://x.com/intent/tweet?text={tweet}")
        self.update_status(f"Shared rating for {place['name']} on X")
        if self.user_prefs['voice_enabled']:
            self.read_status(f"Shared rating for {place['name']} on X")

    def cache_map_offline(self):
        if not self.current_location or not self.nearby_places:
            messagebox.showwarning("Warning", "Search a location to cache data")
            return
        try:
            with open(self.map_file, 'r', encoding='utf-8') as f:
                map_html = f.read()
            self.offline_cache['map'] = map_html
            self.offline_cache['places'] = self.nearby_places
            self.offline_cache['location'] = self.current_location
            with open('wheelmate_offline.json', 'w') as f:
                json.dump(self.offline_cache, f)
            self.user_prefs['offline_mode'] = True
            self.save_preferences()
            self.update_status("Map and data cached for offline use")
            if self.user_prefs['voice_enabled']:
                self.read_status("Map and data cached for offline use")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to cache data: {str(e)}")

    def generate_audit_report(self):
        if not self.nearby_places:
            messagebox.showwarning("Warning", "No places to include in report")
            return
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Error", "PDF generation requires 'reportlab'. Install it with 'pip install reportlab'.")
            self.update_status("PDF generation failed: reportlab not installed")
            return
        try:
            c = canvas.Canvas("wheelmate_audit_report.pdf", pagesize=letter)
            c.drawString(100, 750, "WheelMate Pro Accessibility Audit Report")
            c.drawString(100, 730, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            c.drawString(100, 710, f"Location: {self.search_entry.get()}")
            c.drawString(100, 690, f"User: {self.user_profile['username']}")
            y = 660
            for place in self.nearby_places[:20]:
                c.drawString(100, y, f"Venue: {place['name']}")
                c.drawString(120, y-15, f"Type: {place['type'].capitalize()}")
                c.drawString(120, y-30, f"Accessibility: {self._rating_text(place['rating'])}")
                c.drawString(120, y-45, f"Features: {place['description']}")
                c.drawString(120, y-60, f"Slope: {place['slope'] if place['slope'] is not None else 'Unknown'}°")
                c.drawString(120, y-75, f"Door Width: {place['door_width'] if place['door_width'] is not None else 'Unknown'} cm")
                c.drawString(120, y-90, f"Surface: {place['surface'].capitalize()}")
                with self.db_lock:
                    c = self.db_conn.cursor()
                    c.execute("SELECT COUNT(*) FROM verifications WHERE place_name=?", (place['name'],))
                    verifications = c.fetchone()[0]
                c.drawString(120, y-105, f"Verifications: {verifications}")
                y -= 120
                if y < 50:
                    c.showPage()
                    y = 750
            c.save()
            messagebox.showinfo("Success", "Audit report saved as wheelmate_audit_report.pdf")
            self.update_status("Generated accessibility audit report")
            if self.user_prefs['voice_enabled']:
                self.read_status("Generated accessibility audit report")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate PDF: {str(e)}")
            self.update_status("PDF generation failed")

    def plan_accessible_route(self):
        selected = self.location_tree.focus()
        if not selected or not self.current_location:
            messagebox.showwarning("Warning", "Select a place and search a location first")
            return
        item = self.location_tree.item(selected)
        place_name = item['values'][0]
        for place in self.nearby_places:
            if place['name'] == place_name:
                self.executor.submit(self._fetch_route, place)
                break

    def _fetch_route(self, place):
        try:
            url = "https://api.openrouteservice.org/v2/directions/wheelchair/geojson"
            headers = {'Authorization': '5b3ce3597851110001cf624808f781d9be124f6bbe784d2057dd7e4d'}
            body = {
                "coordinates": [
                    [self.current_location[1], self.current_location[0]],
                    [place['lon'], place['lat']]
                ],
                "preference": "recommended",
                "attributes": ["accessibility"],
                "restrictions": {
                    "maximum_incline": self.user_profile['max_slope'],
                    "surface_type": self.user_profile['preferred_surface']
                }
            }
            response = requests.post(url, json=body, headers=headers, timeout=5)
            if response.status_code == 200:
                route = response.json()
                self.root.after(0, lambda: self._add_route_to_map(route, place))
                self.root.after(0, lambda: self.update_status(f"Accessible route planned to {place['name']}"))
                if self.user_prefs['voice_enabled']:
                    self.root.after(0, lambda: self.read_status(f"Accessible route planned to {place['name']}"))
            else:
                raise Exception(f"API error: {response.status_code}")
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to plan route: {str(e)}"))
            self.root.after(0, lambda: self.update_status("Route planning failed"))

    def _add_route_to_map(self, route, place):
        if not self.current_location:
            return
        m = folium.Map(location=self.current_location, zoom_start=13)
        marker_cluster = MarkerCluster().add_to(m)
        folium.Marker(
            location=self.current_location,
            popup="Your Location",
            icon=folium.Icon(color='blue', icon='user')
        ).add_to(marker_cluster)
        folium.Marker(
            location=[place['lat'], place['lon']],
            popup=f"{place['name']}<br>{self._rating_text(place['rating'])}",
            icon=folium.Icon(color='red', icon='flag')
        ).add_to(marker_cluster)
        coordinates = route['features'][0]['geometry']['coordinates']
        coords = [[lat, lon] for lon, lat in coordinates]
        folium.PolyLine(coords, color='blue', weight=5, opacity=0.7).add_to(m)
        for p in self.nearby_places:
            if p['name'] != place['name']:
                folium.CircleMarker(
                    location=[p['lat'], p['lon']],
                    radius=8,
                    popup=f"{p['name']}<br>{self._rating_text(p['rating'])}",
                    color=self._rating_color(p['rating']),
                    fill=True,
                    fill_color=self._rating_color(p['rating']),
                    fill_opacity=0.7
                ).add_to(marker_cluster)
        MousePosition().add_to(m)
        MeasureControl().add_to(m)
        m.save(self.map_file)
        self.open_map_in_browser()

    def find_nearest_accessible(self):
        if not self.current_location or not self.nearby_places:
            messagebox.showwarning("Warning", "Search a location first")
            return
        accessible = [p for p in self.nearby_places if p['rating'] == 3]
        if not accessible:
            messagebox.showinfo("Info", "No fully accessible places found")
            return
        distances = self._calculate_distances(self.current_location, accessible)
        nearest_idx = np.argmin(distances)
        nearest = accessible[nearest_idx]
        distance = distances[nearest_idx]
        messagebox.showinfo("Nearest Accessible", 
                          f"{nearest['name']} ({nearest['type'].capitalize()})\n"
                          f"Distance: {distance:.1f} km\n"
                          f"Features: {nearest['description']}")
        self.update_status(f"Nearest accessible place: {nearest['name']}")
        if self.user_prefs['voice_enabled']:
            self.read_status(f"Nearest accessible place: {nearest['name']}, {distance:.1f} kilometers")

    def schedule_update_display(self):
        if not self.update_pending:
            self.update_pending = True
            self.root.after(100, self._execute_update_display)

    def _execute_update_display(self):
        self._update_map()
        self._update_location_list()
        self._update_stats()
        self.update_pending = False

    def _update_map(self):
        if not self.current_location:
            return
        m = folium.Map(location=self.current_location, zoom_start=13)
        marker_cluster = MarkerCluster().add_to(m)
        for place in self.nearby_places[:50]:
            folium.CircleMarker(
                location=[place['lat'], place['lon']],
                radius=8,
                popup=f"{place['name']}<br>{self._rating_text(place['rating'])}",
                color=self._rating_color(place['rating']),
                fill=True,
                fill_color=self._rating_color(place['rating']),
                fill_opacity=0.7
            ).add_to(marker_cluster)
        folium.Marker(
            location=self.current_location,
            popup="Your Location",
            icon=folium.Icon(color='blue', icon='user')
        ).add_to(m)
        MousePosition().add_to(m)
        MeasureControl().add_to(m)
        m.save(self.map_file)

    def _update_location_list(self):
        if not self.nearby_places or not self.current_location:
            self.location_tree.delete(*self.location_tree.get_children())
            return
        distances = self._calculate_distances(self.current_location, self.nearby_places)
        places_with_dist = [(dist, place) for dist, place in zip(distances, self.nearby_places) if dist < self.search_radius]
        places_with_dist.sort(key=lambda x: (x[0], -x[1]['rating']))
        current_items = {self.location_tree.item(iid, 'values')[0]: iid for iid in self.location_tree.get_children()}
        new_places = set()
        for dist, place in places_with_dist[:50]:
            new_places.add(place['name'])
            with self.db_lock:
                c = self.db_conn.cursor()
                c.execute("SELECT COUNT(*) FROM verifications WHERE place_name=?", (place['name'],))
                verifications = c.fetchone()[0]
            verified = "Yes" if verifications > 0 else "No"
            values = (
                place['name'],
                f"{dist:.1f} km",
                self._rating_text(place['rating']),
                place['type'].capitalize(),
                verified
            )
            tags = (f"rating_{place['rating']}", 'verified' if verifications > 0 else '')
            if place['name'] in current_items:
                self.location_tree.item(current_items[place['name']], values=values, tags=tags)
            else:
                self.location_tree.insert("", "end", values=values, tags=tags)
        for name, iid in current_items.items():
            if name not in new_places:
                self.location_tree.delete(iid)

    def _update_stats(self):
        if not self.nearby_places or not self.current_location:
            self.stats_label.config(text="Search a location to see statistics")
            for rating in [3, 2, 1, 0]:
                self.progress_bars[rating]['value'] = 0
            return
        distances = self._calculate_distances(self.current_location, self.nearby_places)
        nearby = [p for d, p in zip(distances, self.nearby_places) if d < self.search_radius]
        if not nearby:
            self.stats_label.config(text="No accessibility data for this area")
            return
        total = len(nearby)
        stats = {
            0: len([p for p in nearby if p['rating'] == 0]),
            1: len([p for p in nearby if p['rating'] == 1]),
            2: len([p for p in nearby if p['rating'] == 2]),
            3: len([p for p in nearby if p['rating'] == 3])
        }
        for rating, count in stats.items():
            percentage = (count / total) * 100 if total > 0 else 0
            self.progress_bars[rating]['value'] = percentage
        with self.db_lock:
            c = self.db_conn.cursor()
            c.execute("SELECT COUNT(*) FROM verifications")
            total_verifications = c.fetchone()[0]
        stats_text = f"""Accessibility Stats ({self.search_radius:.1f} km):
📍 Places: {total}
🏷️ Rated: {total - stats[0]} ({100 - stats[0]/total*100:.0f}%)
🟢 Fully: {stats[3]} ({stats[3]/total*100:.0f}%)
🟡 Partial: {stats[2]} ({stats[2]/total*100:.0f}%)
🔴 Limited: {stats[1]} ({stats[1]/total*100:.0f}%)
✅ Verifications: {total_verifications}"""
        self.stats_label.config(text=stats_text)
        if self.user_prefs['voice_enabled']:
            self.read_status(stats_text)

    def on_location_select(self, event):
        selected = self.location_tree.focus()
        if selected:
            item = self.location_tree.item(selected)
            place_name = item['values'][0]
            self.update_status(f"Selected: {place_name}")

    def on_location_double_click(self, event):
        selected = self.location_tree.focus()
        if selected:
            item = self.location_tree.item(selected)
            place_name = item['values'][0]
            for place in self.nearby_places:
                if place['name'] == place_name:
                    details = (f"Name: {place['name']}\n"
                              f"Type: {place['type'].capitalize()}\n"
                              f"Accessibility: {self._rating_text(place['rating'])}\n"
                              f"Distance: {item['values'][1]}\n"
                              f"Features: {place['description']}\n"
                              f"Slope: {place['slope'] if place['slope'] is not None else 'Unknown'}°\n"
                              f"Door Width: {place['door_width'] if place['door_width'] is not None else 'Unknown'} cm\n"
                              f"Surface: {place['surface'].capitalize()}")
                    messagebox.showinfo("Place Details", details)
                    if self.user_prefs['voice_enabled']:
                        self.read_status(details)
                    break

    def on_tree_hover(self, event):
        item = self.location_tree.identify_row(event.y)
        if item:
            try:
                self.location_tree.selection_set(item)
                current_tags = self.location_tree.item(item)['tags']
                if isinstance(current_tags, list):
                    new_tags = ('hover',) + tuple(current_tags)
                else:
                    new_tags = ('hover',) + current_tags
                self.location_tree.item(item, tags=new_tags)
            except Exception as e:
                print(f"Error in on_tree_hover: {str(e)}")

    def save_preferences(self):
        try:
            with open('wheelmate_prefs.json', 'w') as f:
                json.dump(self.user_prefs, f)
        except Exception as e:
            print(f"Failed to save preferences: {str(e)}")

    def load_preferences(self):
        try:
            with open('wheelmate_prefs.json', 'r') as f:
                self.user_prefs.update(json.load(f))
        except FileNotFoundError:
            pass

    def save_profile(self):
        try:
            with open('wheelmate_profile.json', 'w') as f:
                json.dump(self.user_profile, f)
        except Exception as e:
            print(f"Failed to save profile: {str(e)}")

    def open_map_in_browser(self):
        if os.path.exists(self.map_file):
            webbrowser.open(f"file://{os.path.abspath(self.map_file)}")
        else:
            messagebox.showwarning("Warning", "Map file not found. Please search a location first.")

    def update_status(self, message):
        self.status_var.set(message)

    def read_status(self, message):
        if self.user_prefs['voice_enabled']:
            self.tts_engine.say(message)
            self.tts_engine.runAndWait()

    def __del__(self):
        if self.db_conn:
            self.db_conn.close()
        self.executor.shutdown()

def main():
    root = tk.Tk()
    app = WheelMatePro(root)
    root.mainloop()

if __name__ == "__main__":
    main()

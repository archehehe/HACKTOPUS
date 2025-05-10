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
        self.executor_shutdown = False
        self.db_conn = None
        self.google_api_key = "YOUR_GOOGLE_API_KEY"
        self.wheelmap_api_key = "YOUR_WHEELMAP_API_KEY"
        self.ors_api_key = "5b3ce3597851110001cf624808f781d9be124f6bbe784d2057dd7e4d"
        self._configure_main_window()
        self._initialize_services()
        self._prompt_for_wheelmap_key()
        self._setup_database()
        self._load_data()
        self._setup_ui()
        self._show_splash_screen()
        self._show_welcome_message()
        self.root.protocol("WM_DELETE_WINDOW", self.destroy)
        self.use_current_location()

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
        self.current_city = None
        self.search_radius = 10
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
            'default_radius': 10,
            'recent_searches': [],
            'high_contrast': False,
            'voice_enabled': False,
            'offline_mode': False
        }
        self.load_preferences()
        self.offline_cache = {}
        self.db_lock = threading.Lock()
        self.update_pending = False

    def _prompt_for_wheelmap_key(self):
        if self.wheelmap_api_key == "YOUR_WHEELMAP_API_KEY":
            key = simpledialog.askstring(
                "Wheelmap API Key",
                "Enter your Wheelmap API key (get one from https://wheelmap.org/). Leave blank to use OSM/Google Maps only:",
                parent=self.root
            )
            if key:
                self.wheelmap_api_key = key
                self.save_preferences()
            else:
                self.wheelmap_api_key = None
                messagebox.showinfo(
                    "Wheelmap API Key",
                    "No Wheelmap API key provided. Using Google Maps and OpenStreetMap data."
                )

    def _setup_database(self):
        self.db_conn = sqlite3.connect('wheelmate_cache.db', check_same_thread=False)
        c = self.db_conn.cursor()
        expected_columns = [
            'name TEXT', 'lat REAL', 'lon REAL', 'rating INTEGER', 'type TEXT',
            'description TEXT', 'features TEXT', 'last_updated TEXT',
            'slope REAL', 'door_width INTEGER', 'surface TEXT', 'photo BLOB'
        ]
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='places'")
        if c.fetchone():
            c.execute("PRAGMA table_info(places)")
            columns = [col[1] for col in c.fetchall()]
            expected_names = [col.split()[0] for col in expected_columns]
            if len(columns) != len(expected_names) or columns != expected_names:
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

    def destroy(self):
        try:
            if not self.executor_shutdown:
                self.executor.shutdown(wait=False)
                self.executor_shutdown = True
            if self.db_conn:
                self.db_conn.close()
                self.db_conn = None
            self.root.destroy()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

    def __del__(self):
        try:
            if not self.executor_shutdown:
                self.executor.shutdown(wait=False)
                self.executor_shutdown = True
            if self.db_conn:
                self.db_conn.close()
        except Exception:
            pass

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

    def _haversine(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in km using Haversine formula."""
        R = 6371  # Earth's radius in km
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        return R * c

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _fetch_google_places(self, session, lat, lon):
        try:
            places = []
            url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
            params = {
                'location': f"{lat},{lon}",
                'radius': self.search_radius * 1000,
                'key': self.google_api_key,
                'type': 'restaurant|cafe|museum|tourist_attraction|park|store|library|hotel|lodging|bar|night_club',
            }
            # Initial request
            async with session.get(url, params=params, timeout=15) as response:
                if response.status != 200:
                    raise Exception(f"Google Places API error: Status {response.status}")
                data = await response.json()
                if data.get('status') != 'OK':
                    raise Exception(f"Google Places API error: {data.get('status')}")
                results = data.get('results', [])
                next_page_token = data.get('next_page_token')
                places.extend(await self._process_google_places(session, results, lat, lon))
            
            # Handle pagination (up to 2 more pages, max 60 results)
            for _ in range(2):
                if not next_page_token:
                    break
                await asyncio.sleep(2)  # Google requires a delay for next page
                params['pagetoken'] = next_page_token
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status != 200:
                        break
                    data = await response.json()
                    if data.get('status') != 'OK':
                        break
                    results = data.get('results', [])
                    next_page_token = data.get('next_page_token')
                    places.extend(await self._process_google_places(session, results, lat, lon))
            
            # Filter by exact radius using Haversine
            filtered_places = [p for p in places if self._haversine(lat, lon, p['lat'], p['lon']) <= self.search_radius]
            print(f"Google Places fetched {len(filtered_places)} real places within {self.search_radius} km: {[(p['name'], p['rating']) for p in filtered_places]}")
            return filtered_places
        except Exception as e:
            print(f"Google Places API failed: {str(e)}")
            raise

    async def _process_google_places(self, session, results, lat, lon):
        places = []
        for result in results[:50]:
            place_id = result.get('place_id')
            detail_url = "https://maps.googleapis.com/maps/api/place/details/json"
            detail_params = {
                'place_id': place_id,
                'key': self.google_api_key,
                'fields': 'name,types,geometry,formatted_address,wheelchair_accessible_entrance,wheelchair_accessible_restroom,wheelchair_accessible_seating,wheelchair_accessible_parking'
            }
            async with session.get(detail_url, params=detail_params, timeout=15) as detail_response:
                if detail_response.status != 200:
                    continue
                detail_data = await detail_response.json()
                if detail_data.get('status') != 'OK':
                    continue
                place = detail_data.get('result', {})
                has_entrance = place.get('wheelchair_accessible_entrance', False)
                has_restroom = place.get('wheelchair_accessible_restroom', False)
                has_seating = place.get('wheelchair_accessible_seating', False)
                has_parking = place.get('wheelchair_accessible_parking', False)
                if has_entrance and (has_restroom or has_seating or has_parking):
                    rating = 3
                elif has_entrance or has_restroom or has_seating or has_parking:
                    rating = 2
                else:
                    rating = 1
                features = []
                if has_entrance:
                    features.append("Wheelchair-accessible entrance")
                if has_restroom:
                    features.append("Wheelchair-accessible restroom")
                if has_seating:
                    features.append("Wheelchair-accessible seating")
                if has_parking:
                    features.append("Wheelchair-accessible parking")
                places.append({
                    'name': place.get('name', 'Unknown Venue'),
                    'type': place.get('types', ['unknown'])[0],
                    'lat': place.get('geometry', {}).get('location', {}).get('lat', lat),
                    'lon': place.get('geometry', {}).get('location', {}).get('lng', lon),
                    'rating': rating,
                    'address': place.get('formatted_address', f"Near {self.current_city}"),
                    'description': ", ".join(features) or "Accessibility details unavailable",
                    'features': ", ".join(features),
                    'last_updated': datetime.now().strftime('%Y-%m-%d'),
                    'slope': None,
                    'door_width': None,
                    'surface': 'unknown',
                    'photo': None
                })
        return places

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _fetch_osm_data(self, session, lat, lon):
        overpass_url = "http://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:15];
        (
            node["wheelchair"](around:{self.search_radius*1000},{lat},{lon});
            way["wheelchair"](around:{self.search_radius*1000},{lat},{lon});
            node["amenity"]["wheelchair"](around:{self.search_radius*1000},{lat},{lon});
            node["shop"]["wheelchair"](around:{self.search_radius*1000},{lat},{lon});
            node["tourism"]["wheelchair"](around:{self.search_radius*1000},{lat},{lon});
            node["destination"]["wheelchair"](around:{self.search_radius*1000},{lat},{lon});
            way["highway"]["wheelchair"](around:{self.search_radius*1000},{lat},{lon});
        );
        out body;
        """
        try:
            async with session.get(overpass_url, params={'data': query}, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"OSM fetched {len(data['elements'])} real elements")
                    return data['elements']
                raise Exception(f"OSM API error: Status {response.status}")
        except Exception as e:
            print(f"OSM API failed: {str(e)}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _fetch_wheelmap_data(self, session, lat, lon):
        if not self.wheelmap_api_key:
            return []
        # Convert radius (km) to degrees (approx 1 degree = 111 km)
        deg = self.search_radius / 111
        bbox = f"{lon-deg},{lat-deg},{lon+deg},{lat+deg}"
        wheelmap_url = f"https://wheelmap.org/api/nodes?bbox={bbox}&api_key={self.wheelmap_api_key}"
        try:
            async with session.get(wheelmap_url, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"Wheelmap fetched {len(data['nodes'])} real nodes")
                    return data['nodes']
                raise Exception(f"Wheelmap API error: Status {response.status}")
        except Exception as e:
            print(f"Wheelmap API failed: {str(e)}")
            raise

    def _fetch_real_places(self, lat, lon):
        places = []
        if self.user_prefs.get('offline_mode', False):
            places = self._fetch_cached_places(lat, lon)
            print(f"Offline mode: Returned {len(places)} real cached places")
            return places

        async def fetch_all():
            async with aiohttp.ClientSession() as session:
                try:
                    google_task = self._fetch_google_places(session, lat, lon)
                    osm_task = self._fetch_osm_data(session, lat, lon)
                    wheelmap_task = self._fetch_wheelmap_data(session, lat, lon)
                    google_data, osm_data, wheelmap_data = await asyncio.gather(
                        google_task, osm_task, wheelmap_task, return_exceptions=True
                    )

                    if isinstance(google_data, list):
                        places.extend(google_data)
                        print(f"Added {len(google_data)} Google places")

                    if isinstance(osm_data, list):
                        for node in osm_data:
                            tags = node.get('tags', {})
                            rating = {'yes': 3, 'limited': 2, 'no': 1}.get(tags.get('wheelchair'), 0)
                            features = tags.get('wheelchair:description', '') or tags.get('access', '')
                            place_type = tags.get('amenity') or tags.get('shop') or tags.get('tourism') or tags.get('destination') or 'unknown'
                            slope = float(tags.get('highway:incline', 0)) if tags.get('highway:incline') else None
                            door_width = int(tags.get('door:width', 0)) if tags.get('door:width') else None
                            surface = tags.get('surface', 'unknown')
                            place = {
                                'name': tags.get('name', f"{place_type.capitalize()} at {self.current_city}"),
                                'type': place_type,
                                'lat': node['lat'],
                                'lon': node['lon'],
                                'rating': rating,
                                'address': tags.get('addr:street', f"Near {self.current_city}"),
                                'description': features or "Accessible venue with standard features",
                                'features': features,
                                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                                'slope': slope,
                                'door_width': door_width,
                                'surface': surface,
                                'photo': None
                            }
                            if self._haversine(lat, lon, place['lat'], place['lon']) <= self.search_radius:
                                places.append(place)
                        print(f"Added {len(osm_data)} OSM places (after radius filter)")

                    if isinstance(wheelmap_data, list):
                        for node in wheelmap_data:
                            props = node.get('node', {})
                            rating = {'fully_accessible': 3, 'partially_accessible': 2, 'not_accessible': 1}.get(props.get('wheelchair'), 0)
                            place = {
                                'name': props.get('name', f"Venue at {self.current_city}"),
                                'type': props.get('category', 'unknown'),
                                'lat': node['lat'],
                                'lon': node['lon'],
                                'rating': rating,
                                'address': f"Near {self.current_city}",
                                'description': props.get('wheelchair_description', 'Accessibility details available'),
                                'features': props.get('wheelchair_description', ''),
                                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                                'slope': None,
                                'door_width': None,
                                'surface': 'unknown',
                                'photo': None
                            }
                            if self._haversine(lat, lon, place['lat'], place['lon']) <= self.search_radius:
                                places.append(place)
                        print(f"Added {len(wheelmap_data)} Wheelmap places (after radius filter)")

                except Exception as e:
                    print(f"API fetch error: {str(e)}")
                    self.root.after(0, lambda: messagebox.showwarning("API Error", f"Failed to fetch real data: {str(e)}. Using cached data."))
                    places.extend(self._fetch_cached_places(lat, lon))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(fetch_all())
        loop.close()

        unique_places = []
        seen = set()
        for place in places:
            key = (place['name'].lower(), round(place['lat'], 4), round(place['lon'], 4))
            if key not in seen and place['rating'] in [1, 2, 3]:
                seen.add(key)
                unique_places.append(place)
        print(f"Total real places fetched (after filtering): {len(unique_places)}")
        return unique_places[:200]

    def _fetch_cached_places(self, lat, lon):
        try:
            with self.db_lock:
                c = self.db_conn.cursor()
                c.execute("""
                    SELECT * FROM places 
                    WHERE ABS(lat - ?) <= ? AND ABS(lon - ?) <= ?
                """, (lat, self.search_radius / 110, lon, self.search_radius / 110))
                places = []
                for row in c.fetchall():
                    place = {
                        'name': row[0], 'lat': row[1], 'lon': row[2], 'rating': row[3],
                        'type': row[4], 'description': row[5], 'features': row[6],
                        'last_updated': row[7], 'slope': row[8], 'door_width': row[9],
                        'surface': row[10], 'photo': row[11]
                    }
                    if self._haversine(lat, lon, place['lat'], place['lon']) <= self.search_radius:
                        places.append(place)
                return places
        except Exception as e:
            print(f"Cache fetch error: {str(e)}")
            return []

    def _is_cache_valid(self):
        try:
            c = self.db_conn.cursor()
            c.execute("SELECT last_updated FROM places LIMIT 1")
            row = c.fetchone()
            if row:
                last_updated = datetime.strptime(row[0], '%Y-%m-%d')
                return (datetime.now() - last_updated).days < 7
            return False
        except Exception:
            return False

    def _cache_places(self, places):
        try:
            with self.db_lock:
                c = self.db_conn.cursor()
                for place in places:
                    c.execute("""
                        INSERT OR REPLACE INTO places 
                        (name, lat, lon, rating, type, description, features, last_updated, slope, door_width, surface, photo)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        place['name'], place['lat'], place['lon'], place['rating'], place['type'],
                        place['description'], place['features'], place['last_updated'],
                        place['slope'], place['door_width'], place['surface'], place['photo']
                    ))
                self.db_conn.commit()
        except Exception as e:
            print(f"Cache save error: {str(e)}")

    def _get_fallback_places(self, lat, lon):
        types = ['cafe', 'restaurant', 'museum', 'park', 'library', 'hotel', 'bar']
        places = []
        # Generate places in all 4 quadrants
        for i in range(12):
            angle = i * (2 * math.pi / 12)  # Evenly spaced angles
            dist = random.uniform(0.1, self.search_radius)
            dlat = (dist / 111) * math.cos(angle)  # 1 degree ≈ 111 km
            dlon = (dist / (111 * math.cos(math.radians(lat)))) * math.sin(angle)
            places.append({
                'name': f"{random.choice(types).capitalize()} {i+1}",
                'type': random.choice(types),
                'lat': lat + dlat,
                'lon': lon + dlon,
                'rating': random.randint(1, 3),
                'address': f"Near {self.current_city}",
                'description': "Sample accessible venue",
                'features': "Wheelchair-accessible entrance",
                'last_updated': datetime.now().strftime('%Y-%m-%d'),
                'slope': None,
                'door_width': None,
                'surface': 'unknown',
                'photo': None
            })
        print(f"Generated {len(places)} fallback places")
        return places

    def _perform_search(self, query):
        try:
            location = self.geocode(query)
            if not location:
                raise Exception("Location not found")
            self.current_location = (location.latitude, location.longitude)
            city = location.raw.get('address', {}).get('city', 'Unknown')
            self.current_city = city if city != 'Unknown' else self.current_city or 'Paris'
            self.root.after(0, lambda: self.search_entry.delete(0, tk.END))
            self.root.after(0, lambda: self.search_entry.insert(0, location.address))
            if query not in self.user_prefs['recent_searches']:
                self.user_prefs['recent_searches'].insert(0, query)
                self.user_prefs['recent_searches'] = self.user_prefs['recent_searches'][:5]
                self.save_preferences()

            cached_places = self._fetch_cached_places(location.latitude, location.longitude)
            if cached_places and self._is_cache_valid():
                self.nearby_places = cached_places
                status = f"Fetched {len(self.nearby_places)} real cached places near {location.address} ({self.current_city})"
            else:
                self.nearby_places = self._fetch_real_places(location.latitude, location.longitude)
                if self.nearby_places:
                    self._cache_places(self.nearby_places)
                    status = f"Fetched {len(self.nearby_places)} real places near {location.address} ({self.current_city})"
                else:
                    self.nearby_places = self._get_fallback_places(location.latitude, location.longitude)
                    self._cache_places(self.nearby_places)
                    status = f"No real data found. Showing {len(self.nearby_places)} realistic nearby places near {location.address} ({self.current_city})"

            self.root.after(0, self.schedule_update_display)
            self.root.after(0, lambda: self.update_status(status))
            if self.user_prefs['voice_enabled']:
                self.root.after(0, lambda: self.read_status(status))
        except Exception as e:
            error_msg = f"Search failed: {str(e)}"
            self.root.after(0, lambda: messagebox.showerror("Error", error_msg))
            self.root.after(0, lambda: self.update_status(error_msg))

    def _update_map(self, center=None):
        try:
            if not self.current_location:
                return
            center = center or [self.current_location[0], self.current_location[1]]
            # Adjust zoom based on radius
            zoom = max(10, min(15, int(15 - math.log2(self.search_radius))))
            m = folium.Map(location=center, zoom_start=zoom, tiles='CartoDB positron')
            marker_cluster = MarkerCluster().add_to(m)
            quadrants = {'NE': 0, 'NW': 0, 'SE': 0, 'SW': 0}
            for place in self.nearby_places:
                dist = self._haversine(self.current_location[0], self.current_location[1], place['lat'], place['lon'])
                if dist <= self.search_radius and place['rating'] in [1, 2, 3]:
                    # Determine quadrant
                    dlat = place['lat'] - self.current_location[0]
                    dlon = place['lon'] - self.current_location[1]
                    quadrant = 'NE' if dlat >= 0 and dlon >= 0 else 'NW' if dlat >= 0 else 'SE' if dlon >= 0 else 'SW'
                    quadrants[quadrant] += 1
                    popup_text = (f"<b>{place['name']}</b><br>"
                                f"Type: {place['type'].capitalize()}<br>"
                                f"Accessibility: {self._rating_text(place['rating'])}<br>"
                                f"Features: {place['description']}<br>"
                                f"Distance: {dist:.1f} km")
                    folium.Marker(
                        [place['lat'], place['lon']],
                        popup=popup_text,
                        icon=folium.Icon(color=self._rating_color(place['rating'], light=False).replace('#', ''),
                                      icon='info-sign')
                    ).add_to(marker_cluster)
            folium.Marker(
                [self.current_location[0], self.current_location[1]],
                popup="Your Location",
                icon=folium.Icon(color='blue', icon='star')
            ).add_to(m)
            MousePosition().add_to(m)
            MeasureControl().add_to(m)
            m.save(self.map_file)
            self.update_status("Map updated with accessibility-coded places")
            print(f"Map updated with {len(self.nearby_places)} places. Quadrants: {quadrants}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update map: {str(e)}")
            self.update_status(f"Map update failed: {str(e)}")

    def _rating_text(self, rating):
        return {3: "🟢 Fully Accessible", 2: "🟡 Partially Accessible", 
                1: "🔴 Not Accessible", 0: "⚪ Unknown"}.get(rating, "⚪ Unknown")

    def _rating_color(self, rating, light=False):
        colors = {3: ("#4CAF50", "#C8E6C9"), 2: ("#FFC107", "#FFECB3"), 
                  1: ("#F44336", "#FFCDD2"), 0: ("#757575", "#E0E0E0")}
        return colors.get(rating, ("#757575", "#E0E0E0"))[1 if light else 0]

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
        self.stats_frame = ttk.LabelFrame(self.left_frame, text="📊 Area Statistics", padding=10)
        self.stats_frame.pack(fill=tk.X, pady=5)
        self.stats_label = ttk.Label(self.stats_frame, text="No statistics available.")
        self.stats_label.pack(anchor=tk.W)

    def _build_map_panel(self):
        map_frame = ttk.LabelFrame(self.right_frame, text="🗺️ Map", padding=10)
        map_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.map_browser = ttk.Button(map_frame, text="Open Map in Browser", command=lambda: webbrowser.open(f"file://{os.path.abspath(self.map_file)}"))
        self.map_browser.pack(fill=tk.X, pady=5)

    def _build_location_list(self):
        list_frame = ttk.LabelFrame(self.right_frame, text="📍 Nearby Places", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.location_tree = ttk.Treeview(list_frame, columns=('Name', 'Distance', 'Accessibility', 'Type', 'Verified'), show='headings')
        self.location_tree.heading('Name', text='Name')
        self.location_tree.heading('Distance', text='Distance (km)')
        self.location_tree.heading('Accessibility', text='Accessibility')
        self.location_tree.heading('Type', text='Type')
        self.location_tree.heading('Verified', text='Verified')
        self.location_tree.pack(fill=tk.BOTH, expand=True)
        self.location_tree.bind('<Double-1>', self.show_place_details)

    def _build_status_bar(self):
        self.status_bar = ttk.Label(self.main_frame, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)

    def _add_visual_effects(self):
        pass

    def toggle_theme(self):
        self.user_prefs['theme'] = 'dark' if self.user_prefs['theme'] == 'light' else 'light'
        sv_ttk.set_theme(self.user_prefs['theme'])
        self.save_preferences()

    def toggle_voice(self):
        self.user_prefs['voice_enabled'] = not self.user_prefs['voice_enabled']
        self.save_preferences()

    def show_help(self):
        messagebox.showinfo("Help", "WheelMate Pro helps you find accessible places.\n\n"
                                   "1. Enter a location or use 'My Location'.\n"
                                   "2. Adjust search radius and filters.\n"
                                   "3. View places in the list or map.\n"
                                   "4. Rate and verify accessibility.\n\n"
                                   "For support, visit https://wheelmatepro.com.")

    def search_location(self):
        query = self.search_entry.get()
        if query:
            self._perform_search(query)

    def use_current_location(self):
        try:
            g = geocoder.ip('me')
            if g.ok:
                self.current_location = (g.lat, g.lng)
                location = self.geolocator.reverse((g.lat, g.lng), language='en')
                self.current_city = location.raw.get('address', {}).get('city', 'Unknown')
                self._perform_search(location.address)
            else:
                self._perform_search("Paris, France")
        except Exception:
            self._perform_search("Paris, France")

    def update_radius(self, value):
        self.search_radius = float(value)
        self.radius_label.config(text=f"{self.search_radius:.1f} km")
        if self.current_location:
            self._perform_search(self.search_entry.get() or "Current Location")

    def apply_filters(self):
        pass

    def update_profile(self, event=None):
        self.user_profile['mobility_type'] = self.mobility_combo.get().lower()
        try:
            self.user_profile['max_slope'] = float(self.slope_entry.get())
            self.user_profile['min_door_width'] = int(self.door_width_entry.get())
        except ValueError:
            pass

    def edit_profile(self):
        username = simpledialog.askstring("Edit Profile", "Enter username:", initialvalue=self.user_profile['username'])
        if username:
            self.user_profile['username'] = username
            self._build_profile_panel()

    def upload_profile_picture(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if file_path:
            self.user_profile['profile_picture'] = file_path

    def add_rating(self):
        selected = self.location_tree.selection()
        if selected:
            place_name = self.location_tree.item(selected[0])['values'][0]
            rating = int(self.rating_var.get())
            with self.db_lock:
                c = self.db_conn.cursor()
                c.execute("UPDATE places SET rating = ? WHERE name = ?", (rating, place_name))
                self.db_conn.commit()

    def upload_place_photo(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg")])
        if file_path and self.location_tree.selection():
            place_name = self.location_tree.item(self.location_tree.selection()[0])['values'][0]
            with open(file_path, 'rb') as f:
                photo_data = f.read()
            with self.db_lock:
                c = self.db_conn.cursor()
                c.execute("UPDATE places SET photo = ? WHERE name = ?", (photo_data, place_name))
                self.db_conn.commit()

    def verify_place(self):
        selected = self.location_tree.selection()
        if selected:
            place_name = self.location_tree.item(selected[0])['values'][0]
            with self.db_lock:
                c = self.db_conn.cursor()
                c.execute("INSERT INTO verifications (place_name, user, verified, timestamp) VALUES (?, ?, ?, ?)",
                         (place_name, self.user_profile['username'], 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                self.db_conn.commit()

    def share_rating(self):
        messagebox.showinfo("Share", "Rating shared successfully!")

    def generate_audit_report(self):
        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Error", "Reportlab not installed. Cannot generate PDF.")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF files", "*.pdf")])
        if file_path:
            c = canvas.Canvas(file_path, pagesize=letter)
            c.drawString(100, 750, "WheelMate Pro Accessibility Report")
            y = 700
            for place in self.nearby_places:
                c.drawString(100, y, f"{place['name']}: {self._rating_text(place['rating'])}")
                y -= 20
            c.save()
            messagebox.showinfo("Success", f"Report saved to {file_path}")

    def show_place_details(self, event):
        selected = self.location_tree.selection()
        if selected:
            place_name = self.location_tree.item(selected[0])['values'][0]
            for place in self.nearby_places:
                if place['name'] == place_name:
                    details = (f"Name: {place['name']}\n"
                              f"Type: {place['type'].capitalize()}\n"
                              f"Accessibility: {self._rating_text(place['rating'])}\n"
                              f"Features: {place['description']}\n"
                              f"Address: {place['address']}")
                    messagebox.showinfo("Place Details", details)
                    break

    def schedule_update_display(self):
        if not self.update_pending:
            self.update_pending = True
            self.root.after(100, self.update_display)

    def update_display(self):
        self.location_tree.delete(*self.location_tree.get_children())
        quadrants = {'NE': 0, 'NW': 0, 'SE': 0, 'SW': 0}
        for place in self.nearby_places:
            dist = self._haversine(self.current_location[0], self.current_location[1], place['lat'], place['lon'])
            if dist <= self.search_radius:
                dlat = place['lat'] - self.current_location[0]
                dlon = place['lon'] - self.current_location[1]
                quadrant = 'NE' if dlat >= 0 and dlon >= 0 else 'NW' if dlat >= 0 else 'SE' if dlon >= 0 else 'SW'
                quadrants[quadrant] += 1
                self.location_tree.insert('', tk.END, values=(
                    place['name'], f"{dist:.1f}", self._rating_text(place['rating']),
                    place['type'].capitalize(), 'Yes' if place.get('verified') else 'No'
                ))
        self._update_map()
        self.update_pending = False
        print(f"Location list updated. Quadrants: {quadrants}")

    def update_status(self, message):
        self.status_bar.config(text=message)

    def read_status(self, message):
        self.tts_engine.say(message)
        self.tts_engine.runAndWait()

    def _show_splash_screen(self):
        pass

    def _show_welcome_message(self):
        messagebox.showinfo("Welcome", "Welcome to WheelMate Pro! Search for accessible places or use your current location.")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    app = WheelMatePro(root)
    app.run()
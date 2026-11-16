import os
import re
import sqlite3
from datetime import datetime


class DatabaseManager:
    @staticmethod
    def normalize_zone_value(zone_value):
        if zone_value is None:
            return ""
        return ",".join(part.strip() for part in str(zone_value).split(",") if part.strip())

    @staticmethod
    def normalize_zone_list(zone_value):
        if zone_value is None:
            return []
        return [zone.strip().lower() for zone in str(zone_value).split(",") if zone.strip()]

    @staticmethod
    def normalize_plate(plate_number):
        if plate_number is None:
            return ""
        return re.sub(r"[^A-Z0-9-]", "", str(plate_number).upper().strip())

    def __init__(self, db_path="data/surveillance.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicles (
                    plate_number TEXT PRIMARY KEY,
                    owner_name TEXT,
                    vehicle_type TEXT,
                    permitted_zones TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS personnel (
                    person_id TEXT PRIMARY KEY,
                    full_name TEXT,
                    designation TEXT,
                    permitted_zones TEXT,
                    image_filename TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS threat_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    zone TEXT,
                    threat_tier TEXT,
                    entity_type TEXT,
                    entity_identity TEXT,
                    danger_items TEXT,
                    action_taken TEXT
                )
            """)
            conn.commit()

    def add_vehicle(self, plate_number, owner_name, vehicle_type, permitted_zones):
        normalized_plate = self.normalize_plate(plate_number)
        if not normalized_plate:
            raise ValueError("Invalid plate number.")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO vehicles VALUES (?, ?, ?, ?)
            """, (normalized_plate, owner_name.strip(), vehicle_type.strip(), self.normalize_zone_value(permitted_zones)))
            conn.commit()

    def add_person(self, person_id, full_name, designation, permitted_zones, image_filename=""):
        normalized_id = str(person_id).strip().lower()
        if not normalized_id:
            raise ValueError("Invalid person ID.")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO personnel VALUES (?, ?, ?, ?, ?)
            """, (normalized_id, full_name.strip(), designation.strip(), self.normalize_zone_value(permitted_zones), image_filename))
            conn.commit()

    def check_vehicle(self, plate_number, current_zone):
        normalized_plate = self.normalize_plate(plate_number)
        normalized_zone = str(current_zone).strip().lower()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT owner_name, permitted_zones FROM vehicles WHERE plate_number = ?", (normalized_plate,))
            row = cursor.fetchone()
            if row:
                allowed_zones = self.normalize_zone_list(row[1])
                is_authorized = normalized_zone in allowed_zones
                return True, is_authorized, row[0], allowed_zones
            return False, False, "Unknown Owner", []

    def check_personnel(self, person_id, current_zone):
        normalized_id = str(person_id).strip().lower()
        normalized_zone = str(current_zone).strip().lower()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT full_name, permitted_zones FROM personnel WHERE person_id = ?", (normalized_id,))
            row = cursor.fetchone()
            if row:
                allowed_zones = self.normalize_zone_list(row[1])
                is_authorized = normalized_zone in allowed_zones
                return True, is_authorized, row[0], allowed_zones
            return False, False, "Unidentified Person", []

    def get_all_personnel(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT person_id, full_name, designation, permitted_zones, image_filename FROM personnel")
            return cursor.fetchall()

    def get_all_vehicles(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT plate_number, owner_name, vehicle_type, permitted_zones FROM vehicles")
            return cursor.fetchall()

    def log_incident(self, zone, tier, entity_type, identity, danger_items, action):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO threat_logs (timestamp, zone, threat_tier, entity_type, entity_identity, danger_items, action_taken)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts, zone, tier, entity_type, identity, danger_items, action))
            conn.commit()

    def get_recent_logs(self, limit=25):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, zone, threat_tier, entity_type, entity_identity, danger_items, action_taken FROM threat_logs ORDER BY id DESC LIMIT ?", (limit,))
            return cursor.fetchall()
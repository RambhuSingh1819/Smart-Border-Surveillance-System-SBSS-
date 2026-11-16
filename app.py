import os
import re
import sqlite3
import tempfile
import time
import csv
import io

# pyrefly: ignore [missing-import]
import streamlit as st
# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
from PIL import Image
from src.model_hub import ModelHub
from src.db_manager import DatabaseManager
from src.threat_scanner import ThreatScanner
from src.anpr_processor import ANPRProcessor
from src.face_engine import FaceVerifier
from src.security_config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    ALERT_DEDUP_SECONDS,
    BASE_CONFIDENCE,
    REVIEW_REQUIRED_DEFAULT,
    SAFE_PERSON_CONFIDENCE,
    WEAPON_CONFIDENCE,
)

st.set_page_config(page_title="Project 129 - Border Surveillance System", layout="wide")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def sanitize_name(value):
    cleaned = "".join(ch for ch in str(value).strip() if ch.isalnum() or ch in "-_ ")
    return cleaned.strip().lower()


def validate_image_upload(upload, field_name="image"):
    if upload is None:
        return None, "No file selected."

    filename = getattr(upload, "name", "")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None, f"{field_name} must be a JPG or PNG file."

    if getattr(upload, "size", 0) and upload.size > MAX_UPLOAD_BYTES:
        return None, f"{field_name} is too large. Maximum size is 5 MB."

    return filename, "ok"


def save_uploaded_image(upload, destination_dir, file_base_name):
    filename = sanitize_name(file_base_name)
    if not filename:
        raise ValueError("Invalid file base name.")

    ext = os.path.splitext(getattr(upload, "name", ""))[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Unsupported image format.")

    os.makedirs(destination_dir, exist_ok=True)
    final_name = f"{filename}{ext}"
    final_path = os.path.join(destination_dir, final_name)

    with open(final_path, "wb") as f:
        f.write(upload.getvalue())

    return final_name


def next_face_sample_name(person_id, extension=".jpg"):
    os.makedirs("data/authorized_faces", exist_ok=True)
    sample_number = 1
    while os.path.exists(os.path.join("data/authorized_faces", f"{person_id}__{sample_number}{extension}")):
        sample_number += 1
    return f"{person_id}__{sample_number}{extension}"


def validate_plate_number(plate_text):
    if plate_text is None:
        return False
    cleaned = re.sub(r"[^A-Z0-9-]", "", str(plate_text).upper().strip())
    return len(cleaned) >= 4 and len(cleaned) <= 15


def validate_zone_string(zones):
    if zones is None:
        return False
    parts = [zone.strip() for zone in str(zones).split(",") if zone.strip()]
    if not parts:
        return False
    return all(part.replace(" ", "") for part in parts)


def login_required_admin():
    if st.session_state.get("auth_ok"):
        return True

    st.warning("Administrator access is required for registration and review actions.")
    username = st.text_input("Admin username", value=ADMIN_USERNAME)
    password = st.text_input("Admin password", type="password")
    if st.button("Authenticate"):
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state["auth_ok"] = True
            st.success("Admin authentication successful.")
            st.rerun()
        else:
            st.error("Invalid administrator credentials.")
    return False


st.markdown("""
<style>
    .threat-card-critical { background: #fee2e2; border-left: 6px solid #b91c1c; padding: 10px; border-radius: 4px; margin-bottom: 8px; color: #7f1d1d; }
    .threat-card-warning { background: #fef3c7; border-left: 6px solid #d97706; padding: 10px; border-radius: 4px; margin-bottom: 8px; color: #78350f; }
    .threat-card-safe { background: #ecfdf5; border-left: 6px solid #059669; padding: 10px; border-radius: 4px; margin-bottom: 8px; color: #064e3b; }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ Multi-Sensor Border Surveillance & Intrusion Detection System")
st.caption("Project ID: 129 | Faculty Guide: Dr. Suman Yadav | B.Tech Capstone Project (4CSE5)")

@st.cache_resource(show_spinner="⚙️ Loading AI models — this only happens once, please wait...")
def load_system():
    primary, plate_det, weapon_det = ModelHub.get_models()
    db = DatabaseManager()
    anpr = ANPRProcessor(plate_det)
    # FaceVerifier is intentionally lazy — face models load on first detection, not here
    face_verifier = FaceVerifier("data/authorized_faces")
    return primary, plate_det, weapon_det, db, anpr, face_verifier


try:
    primary_model, plate_det, weapon_model, db, anpr_proc, face_verifier = load_system()
except Exception as exc:
    st.error("❌ System failed to start. Check your dependencies and model files.")
    st.exception(exc)
    st.stop()

tabs = st.tabs(["📹 Real-Time Perimeter Feed", "🗄️ Authorizations & Bulk Upload", "📜 Incident Audit Logs"])

# ==================== TAB 2: REGISTRATION & BULK UPLOAD ====================
with tabs[1]:
    admin_authenticated = login_required_admin()
    if admin_authenticated:
        subtab_single, subtab_bulk, subtab_view = st.tabs(["➕ Single Registration (With Photo)", "📦 Bulk Upload (Images & CSV)", "📋 View Authorized Database"])

        # 1. Single Registration
        with subtab_single:
            col_v, col_p = st.columns(2)
            st.write("### 👤 Register Authorized Personnel")
            p_id = st.text_input("Biometric ID / Key (lowercase, e.g. rambhu)", key="single_p_id")
            p_name = st.text_input("Full Official Name", key="single_p_name")
            p_desig = st.text_input("Designation / Role", "Sentry Patrol Lead", key="single_p_desig")
            p_zones = st.text_input("Permitted Sectors", "Perimeter-A,Zone-B,Main-Gate,Supply-Depot", key="single_p_zones")
            
            photo_source = st.radio("Choose Photo Input", ["Upload Photo File", "Capture with Camera"], horizontal=True)
            person_photo = None
            if photo_source == "Upload Photo File":
                person_photo = st.file_uploader("Upload Clear Front Portrait", type=["jpg", "jpeg", "png"], key="single_p_file")
            else:
                person_photo = st.camera_input("Take Biometric Snapshot", key="single_p_cam")

            if st.button("💾 Register & Authorize Person"):
                if p_id and p_name:
                    person_id = sanitize_name(p_id)
                    if not person_id:
                        st.error("Biometric ID contains invalid characters.")
                    elif not validate_zone_string(p_zones):
                        st.error("Please provide at least one valid sector name, separated by commas.")
                    else:
                        filename = f"{person_id}.jpg"
                        save_path = os.path.join("data/authorized_faces", filename)
                        os.makedirs("data/authorized_faces", exist_ok=True)

                        if person_photo:
                            file_name, status = validate_image_upload(person_photo, "Portrait")
                            if status != "ok":
                                st.error(status)
                                st.stop()
                            img = Image.open(person_photo).convert("RGB")
                            img.save(save_path)

                        db.add_person(person_id, p_name.strip(), p_desig.strip(), p_zones.strip(), filename)
                        face_verifier.reload_database("data/authorized_faces")
                        st.success(f"✅ Personnel {p_name.strip()} registered and face biometrics indexed live!")
                else:
                    st.error("Please provide both Biometric ID and Full Name.")

            st.write("### Add another live face sample")
            st.caption("Use different angles or lighting for stronger real-time recognition.")
            sample_id = st.text_input("Existing biometric ID", key="sample_person_id")
            sample_photo = st.camera_input("Capture additional enrollment sample", key="sample_person_camera")
            if st.button("Add face sample"):
                normalized_sample_id = sanitize_name(sample_id)
                if not normalized_sample_id or sample_photo is None:
                    st.error("Enter an existing biometric ID and capture a photo first.")
                else:
                    sample_name = next_face_sample_name(normalized_sample_id)
                    sample_path = os.path.join("data/authorized_faces", sample_name)
                    Image.open(sample_photo).convert("RGB").save(sample_path)
                    face_verifier.reload_database("data/authorized_faces")
                    st.success(f"Added enrollment sample for {normalized_sample_id}.")

            with col_v:
                st.write("### 🚗 Register Authorized Vehicle")
                v_plate = st.text_input("License Plate Number (e.g., UP16AB1234)", key="single_v_plate")
                v_owner = st.text_input("Unit / Owner Name", key="single_v_owner")
                v_type = st.selectbox("Vehicle Type", ["Tactical SUV", "Heavy Supply Truck", "Patrol Car", "Armored Vehicle"], key="single_v_type")
                v_zones = st.text_input("Allowed Sectors", "Perimeter-A,Zone-B,Main-Gate", key="single_v_zones")

                if st.button("💾 Register Vehicle"):
                    if v_plate:
                        if not validate_plate_number(v_plate):
                            st.error("Please enter a valid plate number with only letters, digits, or hyphen.")
                        elif not validate_zone_string(v_zones):
                            st.error("Please provide at least one valid permitted sector for the vehicle.")
                        else:
                            db.add_vehicle(v_plate, v_owner, v_type, v_zones)
                            st.success(f"✅ Vehicle {v_plate.upper()} registered successfully!")
                    else:
                        st.error("Please enter a valid license plate number.")

        # 2. Bulk Upload
        with subtab_bulk:
            st.write("### 📦 Bulk Personnel Images & Vehicle Import")
            col_bulk_p, col_bulk_v = st.columns(2)

            st.info("""
            **Bulk Image Naming Format Options:**
            * Option A: `ID_FullName_Designation_Zone1+Zone2.jpg`  
              *(e.g., `sentry1_John Doe_Officer_Perimeter-A+Zone-B.jpg`)*
            * Option B: `<id>.jpg` *(Will apply batch settings below)*
            """)
            batch_desig = st.text_input("Batch Designation (for Option B)", "Perimeter Guard")
            batch_zones = st.text_input("Batch Allowed Sectors (for Option B)", "Perimeter-A,Zone-B,Main-Gate")
            
            uploaded_photos = st.file_uploader("Upload Multiple Personnel Photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
            if st.button("⚡ Process & Index All Photos"):
                if uploaded_photos:
                    os.makedirs("data/authorized_faces", exist_ok=True)
                    count = 0
                    for photo in uploaded_photos:
                        file_name, status = validate_image_upload(photo, "Portrait")
                        if status != "ok":
                            st.warning(f"Skipping {photo.name}: {status}")
                            continue

                        raw_name = os.path.splitext(os.path.basename(photo.name))[0]
                        parts = raw_name.split("_")

                        if len(parts) >= 4:
                            p_id, full_name, desig, z_raw = parts[0], parts[1], parts[2], parts[3].replace("+", ",")
                        else:
                            p_id = sanitize_name(raw_name)
                            full_name = raw_name.replace("-", " ").replace("_", " ").title()
                            desig = batch_desig
                            z_raw = batch_zones

                        p_id = sanitize_name(p_id)
                        if not p_id:
                            continue

                        dest_file = f"{p_id}.jpg"
                        dest_path = os.path.join("data/authorized_faces", dest_file)
                        img = Image.open(photo).convert("RGB")
                        img = img.resize((160, 160))
                        img.save(dest_path)

                        db.add_person(p_id, full_name, desig, z_raw, dest_file)
                        count += 1

                    face_verifier.reload_database("data/authorized_faces")
                    st.success(f"🎉 Successfully uploaded and indexed {count} authorized profiles!")
                else:
                    st.warning("Please select files to upload.")

            st.info("""
            **Bulk Vehicle CSV Format:**  
            `plate_number,owner_name,vehicle_type,permitted_zones`
            """)
            vehicle_csv = st.file_uploader("Upload Vehicles CSV", type=["csv"])
            if st.button("⚡ Import Vehicles from CSV"):
                if vehicle_csv:
                    imported_count = 0
                    csv_text = vehicle_csv.getvalue().decode("utf-8-sig")
                    for row in csv.DictReader(io.StringIO(csv_text)):
                        plate_value = str(row.get("plate_number", "")).strip()
                        zones_value = str(row.get("permitted_zones", "")).strip()
                        if not validate_plate_number(plate_value) or not validate_zone_string(zones_value):
                            continue
                        db.add_vehicle(plate_value, str(row.get("owner_name", "Unknown")).strip(), str(row.get("vehicle_type", "Patrol Car")).strip(), zones_value)
                        imported_count += 1
                    st.success(f"🎉 Imported {imported_count} valid vehicles into registry!")
                else:
                    st.warning("Please upload a CSV file.")

        # 3. View Registered Database
        with subtab_view:
            st.write("### 📋 Active Personnel Registry")
            p_data = db.get_all_personnel()
            if p_data:
                st.dataframe([dict(zip(["Biometric ID", "Full Name", "Designation", "Allowed Sectors", "Image File"], row)) for row in p_data], use_container_width=True)
            else:
                st.info("No personnel registered yet.")

            st.write("### 🚗 Active Vehicle Registry")
            v_data = db.get_all_vehicles()
            if v_data:
                st.dataframe([dict(zip(["License Plate", "Owner / Unit", "Type", "Allowed Sectors"], row)) for row in v_data], use_container_width=True)
            else:
                st.info("No vehicles registered yet.")

# ==================== TAB 3: AUDIT LOGS ====================
with tabs[2]:
    st.subheader("Persistent Security Incident Logs")
    logs = db.get_recent_logs(30)
    if logs:
        st.dataframe([dict(zip(["Timestamp", "Sector", "Severity Tier", "Entity", "Identity", "Dangerous Items", "Action Taken"], row)) for row in logs], use_container_width=True)
    else:
        st.info("No security incidents recorded yet.")

# ==================== TAB 1: REAL-TIME OPTICS ====================
with tabs[0]:
    col_stream, col_controls = st.columns([2.3, 1.2])
    
    with col_controls:
        st.subheader("Sector Configuration")
        active_zone = st.selectbox("Active Patrol Sector", ["Perimeter-A", "Zone-B", "Main-Gate", "Supply-Depot"])
        source_opt = st.radio("Perimeter Stream Source", ["Upload Video File", "Webcam Feed"])
        sens = st.slider("Detection Sensitivity", 0.20, 0.85, 0.40)
        weapon_conf = st.slider("Weapon Confidence Threshold", 0.30, 0.95, WEAPON_CONFIDENCE)
        review_required = st.checkbox("Operator review required for high-risk alerts", value=REVIEW_REQUIRED_DEFAULT)
        if not getattr(weapon_model, "is_specialized", False):
            st.warning("Specialized weapon weights are not installed. Knife and firearm detection will be limited until a trained weapon model is placed at models/weapon_detector.pt.")
        st.divider()
        st.subheader("🚨 Live Incident Ticker")
        incident_placeholder = st.empty()

    with col_stream:
        st.subheader(f"Perimeter Optics - [{active_zone}]")
        feed_placeholder = st.empty()
        feed_placeholder.markdown("""
        <div style="
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f2027 100%);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 48px 32px;
            text-align: center;
            min-height: 420px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 18px;
        ">
            <div style="font-size: 64px; line-height:1;">🎥</div>
            <div style="color:#94a3b8; font-size:13px; letter-spacing:3px; text-transform:uppercase; font-weight:600;">No Active Feed</div>
            <div style="color:#f1f5f9; font-size:22px; font-weight:700; margin: 4px 0;">Perimeter Monitor Standby</div>
            <div style="color:#64748b; font-size:14px; max-width:360px; line-height:1.7;">
                Select a stream source and start monitoring to begin real-time AI threat analysis.
            </div>
            <div style="display:flex; gap:12px; margin-top:8px; flex-wrap:wrap; justify-content:center;">
                <div style="background:#1e3a5f; border:1px solid #2563eb; border-radius:8px; padding:10px 18px; color:#93c5fd; font-size:13px; font-weight:600;">
                    📁 Option A &nbsp;·&nbsp; Upload MP4 / AVI
                </div>
                <div style="background:#1a3a2a; border:1px solid #16a34a; border-radius:8px; padding:10px 18px; color:#86efac; font-size:13px; font-weight:600;">
                    📷 Option B &nbsp;·&nbsp; Live Webcam
                </div>
            </div>
            <div style="margin-top:18px; display:flex; gap:10px; align-items:center; background:#0f172a; border:1px solid #22c55e33; border-radius:8px; padding:8px 20px;">
                <span style="width:9px;height:9px;border-radius:50%;background:#22c55e;display:inline-block;box-shadow:0 0 8px #22c55e;"></span>
                <span style="color:#4ade80; font-size:12px; font-weight:600; letter-spacing:1px;">AI SYSTEMS ONLINE &nbsp;·&nbsp; AWAITING FEED INPUT</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    cap = None
    start_monitoring = False
    if source_opt == "Webcam Feed":
        start_monitoring = st.button("▶️ Start Webcam Monitoring")
        if start_monitoring:
            cap = cv2.VideoCapture(0)
    else:
        video_file = st.file_uploader("Upload Surveillance MP4/AVI", type=["mp4", "avi", "mov"])
        if video_file:
            tfile = tempfile.NamedTemporaryFile(delete=False)
            tfile.write(video_file.read())
            start_monitoring = st.button("▶️ Start Uploaded Video")
            if start_monitoring:
                cap = cv2.VideoCapture(tfile.name)

    if cap and cap.isOpened():
        stop_stream = st.button("⏹️ Stop Monitoring Feed")
        live_logs = []

        alert_cache = {}
        while not stop_stream:
            ret, frame = cap.read()
            if not ret:
                st.info("Feed disconnected or video completed.")
                break

            people, vehicles, weapons = ThreatScanner.analyze_scene(frame, primary_model, weapon_model, conf_thresh=sens, weapon_conf_thresh=weapon_conf)

            # Process People
            for p in people:
                px1, py1, px2, py2 = p["box"]
                p_crop = frame[py1:py2, px1:px2]

                is_face_auth = False
                identity = "unknown"
                face_score = 0.0
                if p_crop.size > 0:
                    is_face_auth, identity, face_score = face_verifier.verify_crop(p_crop)

                exists, zone_auth, full_name, _ = db.check_personnel(identity, active_zone)

                if p["weapons"]:
                    tier = "Tier 3 (CRITICAL - ARMED THREAT)"
                    color = (0, 0, 255)
                    status_text = f"ARMED: {','.join(p['weapons']).upper()}"
                    alert_key = f"armed:{identity}:{active_zone}:{','.join(p['weapons'])}"
                    if alert_key not in alert_cache or (time.time() - alert_cache[alert_key]) > ALERT_DEDUP_SECONDS:
                        db.log_incident(active_zone, tier, "Person", identity, ",".join(p["weapons"]), "Tactical Alarm Triggered")
                        if review_required:
                            live_logs.insert(0, f"<div class='threat-card-critical'><b>🚨 ARMED INTRUDER | REVIEW REQUIRED</b>: {identity.upper()}<br>Weapons: {','.join(p['weapons'])} | Sector: {active_zone}</div>")
                        else:
                            live_logs.insert(0, f"<div class='threat-card-critical'><b>🚨 ARMED INTRUDER</b>: {identity.upper()}<br>Weapons: {','.join(p['weapons'])} | Sector: {active_zone}</div>")
                        alert_cache[alert_key] = time.time()
                elif not exists:
                    tier = "Tier 3 (UNAUTHORIZED INTRUDER)"
                    color = (0, 0, 255)
                    status_text = "UNAUTHORIZED PERSON"
                    luggage_str = f"Luggage: {','.join(p['luggage'])}" if p['luggage'] else "No Baggage"
                    alert_key = f"intruder:{active_zone}:{luggage_str}"
                    if alert_key not in alert_cache or (time.time() - alert_cache[alert_key]) > ALERT_DEDUP_SECONDS:
                        db.log_incident(active_zone, tier, "Person", "Unknown", luggage_str, "Sentry Intercept")
                        live_logs.insert(0, f"<div class='threat-card-critical'><b>🚨 INTRUSION ALERT</b>: Unregistered Person in {active_zone}<br>{luggage_str}</div>")
                        alert_cache[alert_key] = time.time()
                elif not zone_auth:
                    tier = "Tier 2 (ZONE VIOLATION)"
                    color = (0, 165, 255)
                    status_text = f"OUT OF SECTOR: {full_name}"
                    alert_key = f"zone:{full_name}:{active_zone}"
                    if alert_key not in alert_cache or (time.time() - alert_cache[alert_key]) > ALERT_DEDUP_SECONDS:
                        live_logs.insert(0, f"<div class='threat-card-warning'><b>⚠️ ZONE VIOLATION</b>: {full_name} not authorized in {active_zone}</div>")
                        alert_cache[alert_key] = time.time()
                else:
                    tier = "Tier 1 (AUTHORIZED SENTRY)"
                    color = (0, 255, 0)
                    status_text = f"AUTHORIZED: {full_name} ({face_score:.2f})"

                cv2.rectangle(frame, (px1, py1), (px2, py2), color, 2)
                cv2.putText(frame, status_text, (px1, max(20, py1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
                if p["luggage"]:
                    cv2.putText(frame, f"Carrying: {','.join(p['luggage'])}", (px1, min(frame.shape[0] - 8, py2 + 18)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            # Draw every dangerous-item detection, including items not fully inside a person box.
            for danger in weapons:
                dx1, dy1, dx2, dy2 = danger["box"]
                danger_label = f"DANGER: {danger['label'].upper()}"
                cv2.rectangle(frame, (dx1, dy1), (dx2, dy2), (0, 0, 255), 3)
                cv2.putText(frame, danger_label, (dx1, max(20, dy1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

            # Process Vehicles
            for v in vehicles:
                vx1, vy1, vx2, vy2 = v["box"]
                vcrop = frame[vy1:vy2, vx1:vx2]
                plate_str, _ = anpr_proc.extract_plate(vcrop)

                exists, zone_auth, owner, _ = db.check_vehicle(plate_str, active_zone)

                if plate_str != "UNREADABLE" and not exists:
                    color = (0, 0, 255)
                    v_status = f"UNREGISTERED VEHICLE: {plate_str}"
                    alert_key = f"vehicle:{plate_str}:{active_zone}"
                    if alert_key not in alert_cache or (time.time() - alert_cache[alert_key]) > ALERT_DEDUP_SECONDS:
                        db.log_incident(active_zone, "Tier 3 (UNREGISTERED VEHICLE)", "Vehicle", plate_str, "None", "Gate Blocked")
                        live_logs.insert(0, f"<div class='threat-card-critical'><b>🚨 UNREGISTERED VEHICLE</b>: Plate {plate_str} detected in {active_zone}</div>")
                        alert_cache[alert_key] = time.time()
                elif plate_str != "UNREADABLE" and not zone_auth:
                    color = (0, 165, 255)
                    v_status = f"ZONE RESTRICTED: {plate_str}"
                    alert_key = f"vehicle_zone:{plate_str}:{active_zone}"
                    if alert_key not in alert_cache or (time.time() - alert_cache[alert_key]) > ALERT_DEDUP_SECONDS:
                        live_logs.insert(0, f"<div class='threat-card-warning'><b>⚠️ VEHICLE RESTRICTED</b>: Plate {plate_str} not allowed in {active_zone}</div>")
                        alert_cache[alert_key] = time.time()
                elif exists and zone_auth:
                    color = (0, 255, 0)
                    v_status = f"AUTHORIZED: {plate_str}"
                else:
                    color = (128, 128, 128)
                    v_status = "SCANNING PLATE..."

                cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), color, 2)
                cv2.putText(frame, v_status, (vx1, max(20, vy1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            feed_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB")
            incident_placeholder.markdown("".join(live_logs[:6]), unsafe_allow_html=True)

        cap.release()
    elif not start_monitoring:
        pass  # Placeholder already shown above
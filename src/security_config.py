import os

PRIMARY_MODEL_NAME = os.environ.get("BORDER_PRIMARY_MODEL", "yolov8s.pt")
WEAPON_MODEL_NAME = os.environ.get("BORDER_WEAPON_MODEL", "yolov8m.pt")
PLATE_MODEL_NAME = os.environ.get("BORDER_PLATE_MODEL", "yolov8m.pt")

ALERT_DEDUP_SECONDS = int(os.environ.get("BORDER_ALERT_DEDUP_SECONDS", "8"))
BASE_CONFIDENCE = float(os.environ.get("BORDER_BASE_CONFIDENCE", "0.45"))
WEAPON_CONFIDENCE = float(os.environ.get("BORDER_WEAPON_CONFIDENCE", "0.68"))
SAFE_PERSON_CONFIDENCE = float(os.environ.get("BORDER_SAFE_PERSON_CONFIDENCE", "0.65"))

ADMIN_USERNAME = os.environ.get("BORDER_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("BORDER_ADMIN_PASS", "ChangeMe!2026")
REVIEW_REQUIRED_DEFAULT = os.environ.get("BORDER_REVIEW_REQUIRED", "true").lower() == "true"

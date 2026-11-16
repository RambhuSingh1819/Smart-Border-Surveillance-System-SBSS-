import os
import shutil


class ModelHub:
    @staticmethod
    def get_models():
        # Load Ultralytics only after the Streamlit shell has started.
        from ultralytics import YOLO, YOLOWorld

        os.makedirs("models", exist_ok=True)

        local_fallback = "yolov8n.pt"
        allow_downloads = os.getenv("ALLOW_MODEL_DOWNLOADS", "0") == "1"
        primary_model_path = "models/primary_detector.pt" if os.path.exists("models/primary_detector.pt") else local_fallback

        # 1. Stronger general detector for real-world perimeter work
        primary_model = YOLO(primary_model_path)

        # 2. More capable weapon detector fallback pipeline
        weapon_model_path = "models/weapon_detector.pt"
        if not os.path.exists(weapon_model_path):
            weapon_model_path = local_fallback
        if allow_downloads and weapon_model_path == local_fallback:
            try:
                from huggingface_hub import hf_hub_download
                downloaded_weapon = hf_hub_download(
                    repo_id="foduucom/weapon-detection",
                    filename="best.pt"
                )
                shutil.copy(downloaded_weapon, weapon_model_path)
            except Exception:
                weapon_model_path = local_fallback

        if os.path.exists(weapon_model_path) and weapon_model_path != local_fallback:
            weapon_detector = YOLO(weapon_model_path)
            weapon_detector.is_specialized = True
        elif os.path.exists("yolov8s-worldv2.pt"):
            weapon_detector = YOLOWorld("yolov8s-worldv2.pt")
            weapon_detector.set_classes([
                "knife", "pistol", "rifle", "shotgun", "firearm",
                "grenade", "axe", "machete", "sword", "dagger",
            ])
            weapon_detector.is_specialized = True
        else:
            weapon_detector = YOLO(weapon_model_path)
            weapon_detector.is_specialized = False
        weapon_detector.model_source = getattr(weapon_detector, "ckpt_path", weapon_model_path)

        # 3. License plate sub-detector
        plate_model_path = "models/plate_detector.pt"
        if not os.path.exists(plate_model_path):
            plate_model_path = local_fallback
        if allow_downloads and plate_model_path == local_fallback:
            try:
                from huggingface_hub import hf_hub_download
                downloaded_plate = hf_hub_download(
                    repo_id="keremberke/yolov8m-license-plate-detection",
                    filename="best.pt"
                )
                shutil.copy(downloaded_plate, plate_model_path)
            except Exception:
                plate_model_path = local_fallback

        plate_detector = YOLO(plate_model_path)

        return primary_model, plate_detector, weapon_detector
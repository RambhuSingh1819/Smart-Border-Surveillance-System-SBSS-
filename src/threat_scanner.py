# pyrefly: ignore [missing-import]
import re

# pyrefly: ignore [missing-import]
import numpy as np


class ThreatScanner:
    DANGER_CLASSES = {
        "knife", "scissors", "baseball bat", "gun", "pistol",
        "rifle", "weapon", "firearm", "sword", "dagger", "grenade",
        "handgun", "revolver", "shotgun", "axe", "machete"
    }
    BAGGAGE_CLASSES = {
        "backpack", "handbag", "suitcase", "bag", "luggage"
    }
    EXCLUDED_CLASSES = {"person", "human", "face", "clothing", "tie", "cell phone", "bottle", "phone"}

    @staticmethod
    def normalize_label(label):
        if label is None:
            return ""
        normalized = re.sub(r"[^a-z0-9\s-]", "", str(label).lower())
        return " ".join(normalized.split())

    @classmethod
    def is_weapon_label(cls, label):
        norm = cls.normalize_label(label)
        if not norm or norm in cls.EXCLUDED_CLASSES:
            return False
        if norm in cls.DANGER_CLASSES:
            return True
        weapon_markers = (
            "gun", "pistol", "rifle", "knife", "blade", "dagger", "firearm",
            "weapon", "grenade", "axe", "machete", "revolver", "shotgun",
            "handgun", "sword"
        )
        return any(marker in norm for marker in weapon_markers)

    @staticmethod
    def calculate_box_overlap(person_box, item_box):
        px1, py1, px2, py2 = person_box
        ix1, iy1, ix2, iy2 = item_box

        xx1 = max(px1, ix1)
        yy1 = max(py1, iy1)
        xx2 = min(px2, ix2)
        yy2 = min(py2, iy2)

        w = max(0, xx2 - xx1)
        h = max(0, yy2 - yy1)
        intersection = w * h
        item_area = max(1, (ix2 - ix1) * (iy2 - iy1))

        return intersection / float(item_area)

    @staticmethod
    def deduplicate_items(items):
        unique_items = []
        for item in items:
            box = item["box"]
            duplicate = False
            for existing in unique_items:
                existing_box = existing["box"]
                overlap = ThreatScanner.calculate_box_overlap(existing_box, box)
                if overlap > 0.50 and (item["label"] == existing["label"] or overlap > 0.80):
                    duplicate = True
                    break
            if not duplicate:
                unique_items.append(item)
        return unique_items

    @classmethod
    def analyze_scene(cls, frame, primary_model, weapon_model=None, conf_thresh=0.45, weapon_conf_thresh=0.68):
        primary_res = primary_model(frame, conf=conf_thresh, verbose=False)[0]

        people = []
        vehicles = []
        luggage = []
        weapons = []

        for box in primary_res.boxes:
            cls_id = int(box.cls[0])
            label = cls.normalize_label(primary_model.names[cls_id])
            coords = list(map(int, box.xyxy[0]))

            if label == "person":
                people.append({"box": coords, "weapons": [], "luggage": []})
            elif label in ["car", "truck", "bus", "motorcycle"]:
                vehicles.append({"box": coords, "label": label})
            elif label in cls.BAGGAGE_CLASSES:
                luggage.append({"box": coords, "label": label})
            elif cls.is_weapon_label(label):
                weapons.append({"box": coords, "label": label})

        if weapon_model is not None:
            try:
                weapon_res = weapon_model(frame, conf=weapon_conf_thresh, verbose=False)[0]
                for box in weapon_res.boxes:
                    cls_id = int(box.cls[0])
                    label = cls.normalize_label(weapon_model.names[cls_id])

                    if not label or label in cls.EXCLUDED_CLASSES or label == "person":
                        continue

                    if cls.is_weapon_label(label):
                        coords = list(map(int, box.xyxy[0]))
                        weapons.append({"box": coords, "label": label})
            except Exception:
                pass

        weapons = cls.deduplicate_items(weapons)

        for person in people:
            p_box = person["box"]
            p_area = (p_box[2] - p_box[0]) * (p_box[3] - p_box[1])

            for w in weapons:
                w_box = w["box"]
                w_area = (w_box[2] - w_box[0]) * (w_box[3] - w_box[1])

                if p_area > 0 and (w_area / float(p_area)) > 0.85:
                    continue

                overlap = cls.calculate_box_overlap(p_box, w_box)
                is_contained = (p_box[0] <= w_box[0] <= p_box[2]) and (p_box[1] <= w_box[1] <= p_box[3])

                if overlap > 0.12 or is_contained:
                    if w["label"] not in person["weapons"]:
                        person["weapons"].append(w["label"])

            for l in luggage:
                overlap = cls.calculate_box_overlap(p_box, l["box"])
                is_contained = (p_box[0] <= l["box"][0] <= p_box[2]) and (p_box[1] <= l["box"][1] <= p_box[3])

                if overlap > 0.18 or is_contained:
                    if l["label"] not in person["luggage"]:
                        person["luggage"].append(l["label"])

        return people, vehicles, weapons
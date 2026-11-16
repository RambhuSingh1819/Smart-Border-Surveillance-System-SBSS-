
import re
# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np

class ANPRProcessor:
    def __init__(self, plate_detector):
        self.plate_detector = plate_detector
        self.reader = None

    def _get_reader(self):
        if self.reader is None:
            # Load OCR only when plate recognition is actually requested.
            import easyocr
            self.reader = easyocr.Reader(['en'], gpu=False)
        return self.reader

    def extract_plate(self, vehicle_crop):
        if vehicle_crop is None or not isinstance(vehicle_crop, np.ndarray) or vehicle_crop.size == 0:
            return "UNREADABLE", None

        # Stage 1: Localize license plate inside vehicle crop
        plate_results = self.plate_detector(vehicle_crop, conf=0.25, verbose=False)[0]
        if len(plate_results.boxes) == 0:
            plate_img = vehicle_crop
        else:
            px1, py1, px2, py2 = map(int, plate_results.boxes[0].xyxy[0])
            plate_img = vehicle_crop[py1:py2, px1:px2]

        if plate_img.size == 0:
            return "UNREADABLE", None

        # Stage 2: Adaptive CLAHE Contrast Preprocessing
        gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blurred = cv2.bilateralFilter(enhanced, 11, 17, 17)

        # Stage 3: OCR Transcription
        ocr_res = self._get_reader().readtext(blurred, detail=0)
        raw_text = "".join(ocr_res).upper()
        clean_plate = re.sub(r'[^A-Z0-9]', '', raw_text)

        if not clean_plate or len(clean_plate) < 4:
            return "UNREADABLE", plate_img

        return clean_plate, plate_img

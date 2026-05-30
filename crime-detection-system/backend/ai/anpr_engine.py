"""
CrimeWatch AI — Automatic Number Plate Recognition (ANPR)
Detects license plates in frames and checks against stolen vehicle database.

Pipeline:
  1. YOLO detects vehicle bounding boxes
  2. Crop vehicle region
  3. EasyOCR reads plate text
  4. Match against stolen vehicles JSON database

Usage:
  engine = ANPREngine()
  result = engine.analyze_frame(frame, vehicle_detections)
"""

import os
import cv2
import json
import re
import numpy as np
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger("crimewatch.anpr")

_easyocr_reader = None

def _get_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(['en'], verbose=False)
            logger.info("[ANPR] EasyOCR loaded ✓")
        except ImportError:
            logger.warning("[ANPR] EasyOCR not installed. pip install easyocr")
    return _easyocr_reader


# ── Indian plate regex patterns ───────────────────────────────────────────────
PLATE_PATTERNS = [
    r"[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}",   # MH12AB1234
    r"[A-Z]{2}\d{2}[A-Z]{2}\d{4}",      # DL01AB1234
    r"[A-Z]{2}\d{2}\d{4}",              # UP32 1234
]


class ANPREngine:
    """
    Automatic Number Plate Recognition engine.
    Detects plates, reads text via OCR, checks stolen vehicle DB.
    """

    def __init__(self, stolen_db_path: str = "data/stolen_vehicles.json"):
        self.stolen_db_path = Path(stolen_db_path)
        self.enabled = os.getenv("ANPR_ENABLED", "true").lower() == "true"
        self.stolen_plates: set[str] = set()
        self._load_stolen_db()

        # Plate detection: use morphological ops + contour detection
        # (No separate model needed — works on vehicle crops)

    def _load_stolen_db(self):
        """Load stolen vehicle plate numbers from JSON"""
        self.stolen_db_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.stolen_db_path.exists():
            # Seed with demo data
            demo_data = {
                "stolen_vehicles": [
                    {"plate": "DL01AB1234", "vehicle": "Honda City", "color": "White", "reported": "2024-01-15"},
                    {"plate": "MH12XY5678", "vehicle": "Toyota Innova", "color": "Black", "reported": "2024-02-20"},
                    {"plate": "UP32CD9012", "vehicle": "Maruti Swift", "color": "Red", "reported": "2024-03-10"},
                    {"plate": "KA05EF3456", "vehicle": "Hyundai i20", "color": "Blue", "reported": "2024-04-05"},
                    {"plate": "TN09GH7890", "vehicle": "Tata Nexon", "color": "Grey", "reported": "2024-05-01"},
                ],
                "wanted_vehicles": [
                    {"plate": "RJ14IJ2345", "reason": "Robbery suspect", "priority": "HIGH"},
                    {"plate": "GJ01KL6789", "reason": "Drug trafficking", "priority": "CRITICAL"},
                ]
            }
            with open(self.stolen_db_path, "w") as f:
                json.dump(demo_data, f, indent=2)
            logger.info("[ANPR] Created demo stolen vehicles database")

        with open(self.stolen_db_path) as f:
            data = json.load(f)

        self.stolen_plates = {
            v["plate"].upper().replace(" ", "")
            for v in data.get("stolen_vehicles", [])
        }
        self.wanted_plates = {
            v["plate"].upper().replace(" ", ""): v
            for v in data.get("wanted_vehicles", [])
        }
        self.full_db = data
        logger.info(f"[ANPR] Loaded {len(self.stolen_plates)} stolen + {len(self.wanted_plates)} wanted plates")

    def _preprocess_plate_region(self, img: np.ndarray) -> np.ndarray:
        """Enhance plate region for better OCR accuracy"""
        # Resize to standard height
        h, w = img.shape[:2]
        if h < 50:
            scale = 50 / h
            img = cv2.resize(img, (int(w * scale), 50))

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Bilateral filter to reduce noise while keeping edges
        filtered = cv2.bilateralFilter(gray, 11, 17, 17)

        # Adaptive threshold
        thresh = cv2.adaptiveThreshold(
            filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def _detect_plate_region(self, vehicle_crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Find license plate region within a vehicle crop using contour detection.
        Returns the plate crop or None.
        """
        gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(blurred, 30, 200)

        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:15]

        for contour in contours:
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.018 * peri, True)

            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = w / h if h > 0 else 0

                # License plates are typically 2:1 to 5:1 aspect ratio
                if 1.5 < aspect_ratio < 6.0 and w > 60 and h > 15:
                    plate_crop = vehicle_crop[y:y+h, x:x+w]
                    return plate_crop

        # Fallback: use bottom portion of vehicle (plates are usually at bottom)
        h, w = vehicle_crop.shape[:2]
        return vehicle_crop[int(h * 0.65):h, int(w * 0.1):int(w * 0.9)]

    def read_plate_text(self, plate_img: np.ndarray) -> Optional[str]:
        """Use EasyOCR to read plate text"""
        reader = _get_reader()
        if reader is None:
            return self._fallback_ocr(plate_img)

        try:
            processed = self._preprocess_plate_region(plate_img)
            # EasyOCR works on BGR or grayscale
            results = reader.readtext(processed, detail=0, paragraph=False)

            if results:
                raw_text = " ".join(results).upper().replace(" ", "").replace("-", "")
                # Clean: keep only alphanumeric
                cleaned = re.sub(r"[^A-Z0-9]", "", raw_text)
                return cleaned if len(cleaned) >= 4 else None

        except Exception as e:
            logger.debug(f"[ANPR] OCR error: {e}")

        return None

    def _fallback_ocr(self, plate_img: np.ndarray) -> Optional[str]:
        """
        Fallback when EasyOCR is not available.
        Returns a simulated plate for demo purposes.
        """
        import random
        states = ["DL", "MH", "UP", "KA", "TN", "GJ", "RJ"]
        plate = f"{random.choice(states)}{random.randint(1,99):02d}{chr(random.randint(65,90))}{chr(random.randint(65,90))}{random.randint(1000,9999)}"
        return plate

    def check_plate(self, plate_text: str) -> dict:
        """Check plate against stolen and wanted databases"""
        if not plate_text:
            return {"status": "unknown", "alert": False}

        normalized = plate_text.upper().replace(" ", "").replace("-", "")

        if normalized in self.wanted_plates:
            info = self.wanted_plates[normalized]
            return {
                "status": "WANTED",
                "alert": True,
                "severity": info.get("priority", "HIGH"),
                "reason": info.get("reason", "Wanted vehicle"),
                "plate": normalized,
            }

        if normalized in self.stolen_plates:
            # Find vehicle details
            vehicle_info = next(
                (v for v in self.full_db.get("stolen_vehicles", [])
                 if v["plate"].replace(" ", "") == normalized),
                {}
            )
            return {
                "status": "STOLEN",
                "alert": True,
                "severity": "HIGH",
                "reason": "Stolen vehicle",
                "plate": normalized,
                "vehicle": vehicle_info.get("vehicle", "Unknown"),
                "color": vehicle_info.get("color", "Unknown"),
                "reported": vehicle_info.get("reported", "Unknown"),
            }

        return {"status": "CLEAR", "alert": False, "plate": normalized}

    def analyze_frame(self, frame: np.ndarray, vehicle_bboxes: list[list]) -> dict:
        """
        Full ANPR pipeline on a frame.
        vehicle_bboxes: list of [x1, y1, x2, y2] for each detected vehicle.
        """
        results = []
        annotated = frame.copy()

        for bbox in vehicle_bboxes:
            x1, y1, x2, y2 = bbox
            vehicle_crop = frame[y1:y2, x1:x2]

            if vehicle_crop.size == 0:
                continue

            # Detect plate region
            plate_region = self._detect_plate_region(vehicle_crop)

            # Read plate text
            plate_text = self.read_plate_text(plate_region) if plate_region is not None else None

            # Check database
            check = self.check_plate(plate_text) if plate_text else {"status": "unread", "alert": False}

            result = {
                "bbox": bbox,
                "plate_text": plate_text,
                "check": check,
                "timestamp": datetime.utcnow().isoformat(),
            }
            results.append(result)

            # Annotate frame
            if plate_text:
                color = (0, 0, 255) if check["alert"] else (0, 255, 100)
                label = f"🚗 {plate_text}"
                if check["alert"]:
                    label += f" ⚠ {check['status']}"

                cv2.rectangle(annotated, (x1, y2 - 30), (x2, y2), (0, 0, 0), -1)
                cv2.putText(annotated, label, (x1 + 4, y2 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

                if check["alert"]:
                    # Red border around vehicle
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    # Alert banner
                    banner = f"STOLEN/WANTED: {plate_text}"
                    cv2.rectangle(annotated, (x1, y1 - 30), (x2, y1), (0, 0, 200), -1)
                    cv2.putText(annotated, banner, (x1 + 4, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        alerts = [r for r in results if r["check"].get("alert")]
        return {
            "plates_detected": len(results),
            "alerts": alerts,
            "has_alert": len(alerts) > 0,
            "results": results,
            "annotated_frame": annotated,
        }

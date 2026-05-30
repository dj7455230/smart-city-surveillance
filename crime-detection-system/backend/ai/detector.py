"""
CrimeWatch AI — Unified Detection Engine (v2 — All Features)
Integrates:
  - YOLOv8 object detection
  - Face recognition + criminal DB match
  - ANPR (number plate detection)
  - Crowd density analysis
  - Night vision enhancement
  - Crime classification (fight, weapon, accident, suspicious, riot)
"""

import cv2
import numpy as np
import base64
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from ultralytics import YOLO

from backend.ai.face_recognition_engine import FaceRecognitionEngine
from backend.ai.anpr_engine import ANPREngine
from backend.ai.crowd_analyzer import CrowdAnalyzer
from backend.ai.night_vision import NightVisionEnhancer, EnhancementMode

logger = logging.getLogger("crimewatch.detector")

# ── YOLO class IDs (COCO) ─────────────────────────────────────────────────────
WEAPON_CLASSES   = {43: "knife", 76: "scissors"}
VEHICLE_CLASSES  = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
PERSON_CLASS     = 0

CRIME_COLORS = {
    "weapon":     (0, 0, 255),
    "fight":      (0, 69, 255),
    "accident":   (0, 165, 255),
    "suspicious": (0, 255, 255),
    "riot":       (0, 0, 200),
    "criminal":   (0, 0, 255),
    "stolen_vehicle": (0, 0, 255),
    "normal":     (0, 255, 0),
}

SEVERITY_MAP = {
    "weapon":         "CRITICAL",
    "criminal":       "CRITICAL",
    "riot":           "CRITICAL",
    "stolen_vehicle": "HIGH",
    "fight":          "HIGH",
    "accident":       "HIGH",
    "suspicious":     "MEDIUM",
    "loitering":      "MEDIUM",
    "normal":         "LOW",
}


class CrimeDetector:
    """
    Unified AI detection engine — all features integrated.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.45,
        enable_face: bool = True,
        enable_anpr: bool = True,
        enable_crowd: bool = True,
        enable_night_vision: bool = True,
    ):
        self.confidence = confidence
        self.model_path = model_path
        self.frame_count = 0
        self.evidence_dir = Path("evidence")
        self.evidence_dir.mkdir(exist_ok=True)

        # Load YOLO
        logger.info(f"[Detector] Loading YOLOv8: {model_path}")
        self.model = YOLO(model_path)
        logger.info("[Detector] YOLOv8 ready ✓")

        # Sub-engines
        self.face_engine = FaceRecognitionEngine() if enable_face else None
        self.anpr_engine = ANPREngine() if enable_anpr else None
        self.crowd_analyzer = CrowdAnalyzer() if enable_crowd else None
        self.night_enhancer = NightVisionEnhancer(
            mode=EnhancementMode.AUTO
        ) if enable_night_vision else None

        logger.info("[Detector] All sub-engines initialized ✓")

    # ── Main detection pipeline ───────────────────────────────────────────────

    def detect_frame(self, frame: np.ndarray, camera_id: str = "CAM-01") -> dict:
        """
        Full detection pipeline on a single frame.
        Returns comprehensive detection result.
        """
        self.frame_count += 1

        # 1. Night vision enhancement
        enhanced_frame = frame
        night_mode = False
        if self.night_enhancer:
            enhanced_frame, night_mode = self.night_enhancer.enhance(frame)

        # 2. YOLOv8 inference
        results = self.model(enhanced_frame, conf=self.confidence, verbose=False)[0]

        persons, vehicles, weapons = [], [], []
        all_detections = []

        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            label = self.model.names[cls_id]
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            det = {
                "class_id": cls_id,
                "label": label,
                "confidence": round(conf, 3),
                "bbox": [x1, y1, x2, y2],
            }
            all_detections.append(det)

            if cls_id == PERSON_CLASS:
                persons.append(det)
            if cls_id in VEHICLE_CLASSES:
                vehicles.append(det)
            if cls_id in WEAPON_CLASSES:
                weapons.append(det)

        # 3. Crime classification
        crime_type, max_confidence = self._classify_crime(persons, vehicles, weapons)

        # 4. Face recognition
        face_result = {"face_count": 0, "criminal_matches": [], "has_criminal_match": False}
        if self.face_engine and len(persons) > 0:
            face_result = self.face_engine.analyze_frame(enhanced_frame)
            if face_result["has_criminal_match"]:
                crime_type = "criminal"
                max_confidence = max(max_confidence, face_result["criminal_matches"][0]["confidence"])

        # 5. ANPR
        anpr_result = {"plates_detected": 0, "alerts": [], "has_alert": False}
        if self.anpr_engine and len(vehicles) > 0:
            vehicle_bboxes = [v["bbox"] for v in vehicles]
            anpr_result = self.anpr_engine.analyze_frame(enhanced_frame, vehicle_bboxes)
            if anpr_result["has_alert"]:
                crime_type = "stolen_vehicle"
                max_confidence = max(max_confidence, 0.90)

        # 6. Crowd analysis
        crowd_result = {"person_count": len(persons), "riot_risk": 0.0, "is_alert": False}
        if self.crowd_analyzer and len(persons) >= 2:
            crowd_result = self.crowd_analyzer.analyze(enhanced_frame, persons)
            if crowd_result["is_alert"] and crime_type == "normal":
                crime_type = crowd_result.get("crime_type", "suspicious")
                max_confidence = max(max_confidence, crowd_result.get("riot_risk", 0.5))

        # 7. Annotate frame
        annotated = self._draw_annotations(
            enhanced_frame.copy(), all_detections, crime_type,
            face_result, anpr_result, crowd_result, night_mode
        )

        is_alert = crime_type != "normal"
        result = {
            "frame_id": self.frame_count,
            "camera_id": camera_id,
            "timestamp": datetime.utcnow().isoformat(),
            "crime_type": crime_type,
            "severity": SEVERITY_MAP.get(crime_type, "LOW"),
            "confidence": round(max_confidence, 3),
            "detections": all_detections,
            "person_count": len(persons),
            "vehicle_count": len(vehicles),
            "annotated_frame": annotated,
            "is_alert": is_alert,
            "night_mode": night_mode,
            # Sub-engine results
            "face": face_result,
            "anpr": anpr_result,
            "crowd": crowd_result,
        }

        if is_alert:
            result["snapshot_path"] = self._save_snapshot(annotated, crime_type)

        return result

    # ── Crime classification logic ────────────────────────────────────────────

    def _classify_crime(
        self,
        persons: list,
        vehicles: list,
        weapons: list,
    ) -> tuple[str, float]:
        """Classify crime type from YOLO detections"""

        # Weapon detected → highest priority
        if weapons:
            return "weapon", max(w["confidence"] for w in weapons)

        # Fight: 2+ persons with overlapping boxes
        if len(persons) >= 2 and self._detect_fight(persons):
            return "fight", 0.78

        # Accident: vehicles overlapping
        if len(vehicles) >= 2 and self._detect_accident(vehicles):
            return "accident", 0.72

        # Suspicious: lone person in restricted zone
        if len(persons) == 1 and self._detect_suspicious(persons[0]):
            return "suspicious", 0.58

        return "normal", 0.0

    def _detect_fight(self, persons: list) -> bool:
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                if self._compute_iou(persons[i]["bbox"], persons[j]["bbox"]) > 0.15:
                    return True
        return False

    def _detect_accident(self, vehicles: list) -> bool:
        for i in range(len(vehicles)):
            for j in range(i + 1, len(vehicles)):
                if self._compute_iou(vehicles[i]["bbox"], vehicles[j]["bbox"]) > 0.10:
                    return True
        return False

    def _detect_suspicious(self, person: dict) -> bool:
        x1, y1, x2, y2 = person["bbox"]
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        return cx > 800 and cy > 500

    def _compute_iou(self, box1: list, box2: list) -> float:
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter
        return inter / union if union > 0 else 0.0

    # ── Frame annotation ──────────────────────────────────────────────────────

    def _draw_annotations(
        self,
        frame: np.ndarray,
        detections: list,
        crime_type: str,
        face_result: dict,
        anpr_result: dict,
        crowd_result: dict,
        night_mode: bool,
    ) -> np.ndarray:
        """Draw all annotations on frame"""
        color = CRIME_COLORS.get(crime_type, CRIME_COLORS["normal"])

        # YOLO bounding boxes
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            det_color = CRIME_COLORS.get("weapon", color) if det["class_id"] in WEAPON_CLASSES else color
            cv2.rectangle(frame, (x1, y1), (x2, y2), det_color, 2)
            label = f"{det['label']} {det['confidence']:.0%}"
            cv2.putText(frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, det_color, 1)

        # Face recognition overlays
        if face_result.get("has_criminal_match"):
            for match in face_result["criminal_matches"]:
                x1, y1, x2, y2 = match["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                cv2.putText(frame, f"⚠ CRIMINAL: {match['identity']}",
                            (x1, y1 - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # ANPR overlays (handled inside anpr_engine, but add summary)
        if anpr_result.get("has_alert"):
            for alert in anpr_result["alerts"]:
                plate = alert.get("plate_text", "")
                status = alert["check"].get("status", "")
                x1, y1, x2, y2 = alert["bbox"]
                cv2.putText(frame, f"🚗 {plate} [{status}]",
                            (x1, y2 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

        # Crime alert banner
        if crime_type != "normal":
            severity = SEVERITY_MAP.get(crime_type, "MEDIUM")
            banner_color = {
                "CRITICAL": (0, 0, 180),
                "HIGH":     (0, 50, 180),
                "MEDIUM":   (0, 100, 150),
            }.get(severity, (0, 80, 120))

            cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), banner_color, -1)
            cv2.putText(
                frame,
                f"  ⚠  {crime_type.upper().replace('_', ' ')} DETECTED  |  {severity}",
                (10, 35), cv2.FONT_HERSHEY_DUPLEX, 0.95, (255, 255, 255), 2
            )

        # Crowd stats (if significant)
        if crowd_result.get("person_count", 0) >= 3:
            risk = crowd_result.get("riot_risk", 0)
            cv2.putText(
                frame,
                f"Crowd: {crowd_result['person_count']} | Riot Risk: {risk:.0%}",
                (10, frame.shape[0] - 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (0, 0, 255) if risk > 0.6 else (200, 200, 200), 1
            )

        # Timestamp + camera ID
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, ts, (10, frame.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

        return frame

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _save_snapshot(self, frame: np.ndarray, crime_type: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{crime_type}_{ts}.jpg"
        path = self.evidence_dir / filename
        cv2.imwrite(str(path), frame)
        return str(path)

    def frame_to_base64(self, frame: np.ndarray) -> str:
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return base64.b64encode(buffer).decode("utf-8")

    def process_video_file(self, video_path: str, camera_id: str = "CAM-01"):
        """Generator: yields detection results frame by frame"""
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        skip = max(1, int(fps // 10))
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_idx += 1
            if frame_idx % skip != 0:
                continue
            yield self.detect_frame(frame, camera_id)

        cap.release()

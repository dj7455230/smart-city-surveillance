"""
CrimeWatch AI — Face Recognition Engine
Detects faces in frames and matches against criminal database.

Uses DeepFace (wraps FaceNet / ArcFace / VGG-Face).
Criminal DB is a folder of reference images: criminal_db/<name>/<photo.jpg>

Usage:
  engine = FaceRecognitionEngine()
  result = engine.analyze_frame(frame)
"""

import os
import cv2
import numpy as np
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger("crimewatch.face")

# Lazy import DeepFace to avoid slow startup
_deepface = None

def _get_deepface():
    global _deepface
    if _deepface is None:
        try:
            from deepface import DeepFace
            _deepface = DeepFace
            logger.info("[Face] DeepFace loaded ✓")
        except ImportError:
            logger.warning("[Face] DeepFace not installed. pip install deepface")
    return _deepface


class FaceRecognitionEngine:
    """
    Real-time face detection + criminal database matching.
    Falls back gracefully if DeepFace is not installed.
    """

    def __init__(
        self,
        criminal_db_path: str = "criminal_db",
        model_name: str = "VGG-Face",       # VGG-Face, Facenet, ArcFace
        detector_backend: str = "opencv",    # opencv, retinaface, mtcnn
        distance_metric: str = "cosine",
        threshold: float = 0.40,
    ):
        self.criminal_db_path = Path(criminal_db_path)
        self.model_name = model_name
        self.detector_backend = detector_backend
        self.distance_metric = distance_metric
        self.threshold = threshold
        self.enabled = os.getenv("FACE_RECOGNITION_ENABLED", "true").lower() == "true"

        # Haar cascade as fallback face detector
        self._haar = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

        # Ensure criminal DB directory exists
        self.criminal_db_path.mkdir(parents=True, exist_ok=True)
        self._seed_demo_criminals()

    def _seed_demo_criminals(self):
        """Create placeholder criminal profiles for demo"""
        demo_dir = self.criminal_db_path / "demo_suspect_001"
        if not demo_dir.exists():
            demo_dir.mkdir(parents=True)
            # Create a synthetic face placeholder image
            placeholder = np.zeros((200, 200, 3), dtype=np.uint8)
            placeholder[:] = (60, 60, 80)
            cv2.putText(placeholder, "SUSPECT", (30, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
            cv2.imwrite(str(demo_dir / "photo.jpg"), placeholder)

    def detect_faces(self, frame: np.ndarray) -> list[dict]:
        """
        Detect all faces in frame using Haar cascade (fast, no GPU needed).
        Returns list of face dicts with bbox and crop.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces_raw = self._haar.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )

        faces = []
        for (x, y, w, h) in faces_raw:
            # Add padding
            pad = 20
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(frame.shape[1], x + w + pad)
            y2 = min(frame.shape[0], y + h + pad)

            crop = frame[y1:y2, x1:x2]
            faces.append({
                "bbox": [x1, y1, x2, y2],
                "crop": crop,
                "matched": False,
                "identity": None,
                "confidence": 0.0,
            })

        return faces

    def match_against_db(self, face_crop: np.ndarray) -> dict:
        """
        Match a face crop against the criminal database.
        Returns match result with identity and confidence.
        """
        DeepFace = _get_deepface()
        if DeepFace is None or not self.enabled:
            return {"matched": False, "identity": None, "confidence": 0.0}

        if not any(self.criminal_db_path.iterdir()):
            return {"matched": False, "identity": None, "confidence": 0.0}

        try:
            # Save temp crop
            tmp_path = "tmp_face_crop.jpg"
            cv2.imwrite(tmp_path, face_crop)

            results = DeepFace.find(
                img_path=tmp_path,
                db_path=str(self.criminal_db_path),
                model_name=self.model_name,
                detector_backend=self.detector_backend,
                distance_metric=self.distance_metric,
                enforce_detection=False,
                silent=True,
            )

            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

            if results and len(results[0]) > 0:
                best = results[0].iloc[0]
                dist_col = [c for c in best.index if "distance" in c.lower()]
                distance = float(best[dist_col[0]]) if dist_col else 1.0

                if distance < self.threshold:
                    identity_path = best.get("identity", "")
                    # Extract name from folder structure
                    name = Path(identity_path).parent.name.replace("_", " ").title()
                    confidence = round(1.0 - distance, 3)
                    return {
                        "matched": True,
                        "identity": name,
                        "confidence": confidence,
                        "distance": distance,
                    }

        except Exception as e:
            logger.debug(f"[Face] Match error: {e}")

        return {"matched": False, "identity": None, "confidence": 0.0}

    def analyze_frame(self, frame: np.ndarray) -> dict:
        """
        Full pipeline: detect faces → match against DB → annotate frame.
        Returns analysis result dict.
        """
        faces = self.detect_faces(frame)
        matches = []
        annotated = frame.copy()

        for face in faces:
            x1, y1, x2, y2 = face["bbox"]

            # Try DB match
            match = self.match_against_db(face["crop"])
            face.update(match)

            if match["matched"]:
                # Red box for known criminal
                color = (0, 0, 255)
                label = f"⚠ {match['identity']} ({match['confidence']:.0%})"
                matches.append({
                    "identity": match["identity"],
                    "confidence": match["confidence"],
                    "bbox": face["bbox"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
            else:
                # Yellow box for unknown face
                color = (0, 200, 255)
                label = f"Unknown ({len(faces)} face{'s' if len(faces)>1 else ''})"

            # Draw on frame
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Draw face landmark dots (simulated)
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            for dx, dy in [(-15, -10), (15, -10), (0, 5), (-8, 18), (8, 18)]:
                cv2.circle(annotated, (cx + dx, cy + dy), 2, color, -1)

        return {
            "face_count": len(faces),
            "criminal_matches": matches,
            "has_criminal_match": len(matches) > 0,
            "annotated_frame": annotated,
        }

    def add_criminal_to_db(self, name: str, image: np.ndarray) -> str:
        """Add a new criminal profile to the database"""
        safe_name = name.lower().replace(" ", "_")
        person_dir = self.criminal_db_path / safe_name
        person_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = person_dir / f"{ts}.jpg"
        cv2.imwrite(str(img_path), image)

        logger.info(f"[Face] Added criminal profile: {name} → {img_path}")
        return str(img_path)

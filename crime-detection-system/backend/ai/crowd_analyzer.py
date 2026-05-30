"""
CrimeWatch AI — Crowd Density & Behavior Analyzer
Analyzes crowd size, density, and detects riot/mob formation.

Features:
  - Person count per zone
  - Crowd density heatmap
  - Riot risk scoring
  - Loitering detection (person stationary too long)
  - Panic detection (sudden dispersal)

Usage:
  analyzer = CrowdAnalyzer()
  result = analyzer.analyze(frame, person_detections)
"""

import cv2
import numpy as np
import logging
from datetime import datetime
from collections import deque
from typing import Optional

logger = logging.getLogger("crimewatch.crowd")

# Thresholds
CROWD_THRESHOLDS = {
    "low":      (0, 4),     # 0-4 persons: normal
    "medium":   (5, 9),     # 5-9 persons: monitor
    "high":     (10, 19),   # 10-19 persons: alert
    "critical": (20, 9999), # 20+ persons: riot risk
}

RIOT_RISK_WEIGHTS = {
    "person_count":     0.4,
    "density_score":    0.3,
    "movement_chaos":   0.2,
    "zone_violation":   0.1,
}


class PersonTracker:
    """Simple centroid-based person tracker for loitering detection"""

    def __init__(self, max_history: int = 90):  # 3 seconds at 30fps
        self.tracks: dict[int, deque] = {}
        self.next_id = 0
        self.max_history = max_history

    def update(self, centroids: list[tuple]) -> dict[int, list]:
        """Update tracks with new centroids. Returns {id: [centroid_history]}"""
        if not centroids:
            return {}

        # Simple nearest-neighbor assignment
        if not self.tracks:
            for c in centroids:
                self.tracks[self.next_id] = deque([c], maxlen=self.max_history)
                self.next_id += 1
        else:
            existing_ids = list(self.tracks.keys())
            existing_cents = [self.tracks[i][-1] for i in existing_ids]

            assigned = set()
            for c in centroids:
                # Find nearest existing track
                dists = [np.linalg.norm(np.array(c) - np.array(ec)) for ec in existing_cents]
                if dists:
                    nearest_idx = int(np.argmin(dists))
                    if dists[nearest_idx] < 80 and nearest_idx not in assigned:
                        self.tracks[existing_ids[nearest_idx]].append(c)
                        assigned.add(nearest_idx)
                    else:
                        self.tracks[self.next_id] = deque([c], maxlen=self.max_history)
                        self.next_id += 1

        return {k: list(v) for k, v in self.tracks.items()}

    def get_loiterers(self, min_frames: int = 60, max_movement: float = 30.0) -> list[int]:
        """Return IDs of persons who haven't moved much for min_frames frames"""
        loiterers = []
        for track_id, history in self.tracks.items():
            if len(history) >= min_frames:
                positions = np.array(history[-min_frames:])
                total_movement = np.sum(np.linalg.norm(np.diff(positions, axis=0), axis=1))
                if total_movement < max_movement:
                    loiterers.append(track_id)
        return loiterers


class CrowdAnalyzer:
    """
    Analyzes crowd behavior from person detection results.
    """

    def __init__(self, frame_width: int = 1280, frame_height: int = 720):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.tracker = PersonTracker()
        self.frame_history: deque = deque(maxlen=30)
        self.density_map_history: deque = deque(maxlen=10)

    def _get_crowd_level(self, count: int) -> str:
        for level, (lo, hi) in CROWD_THRESHOLDS.items():
            if lo <= count <= hi:
                return level
        return "critical"

    def _compute_density_map(
        self, centroids: list[tuple], frame_shape: tuple
    ) -> np.ndarray:
        """Generate a density heatmap from person centroids"""
        h, w = frame_shape[:2]
        density = np.zeros((h, w), dtype=np.float32)

        for cx, cy in centroids:
            if 0 <= cx < w and 0 <= cy < h:
                cv2.circle(density, (int(cx), int(cy)), 60, 1.0, -1)

        # Gaussian blur for smooth heatmap
        density = cv2.GaussianBlur(density, (61, 61), 0)
        return density

    def _compute_movement_chaos(self, tracks: dict) -> float:
        """
        Measure how chaotic the crowd movement is.
        High chaos = potential riot/panic.
        Returns 0.0 (calm) to 1.0 (chaotic).
        """
        if len(tracks) < 3:
            return 0.0

        velocities = []
        for history in tracks.values():
            if len(history) >= 5:
                recent = np.array(history[-5:])
                vel = np.diff(recent, axis=0)
                velocities.append(vel.mean(axis=0))

        if len(velocities) < 2:
            return 0.0

        velocities = np.array(velocities)
        # Variance in velocity directions = chaos
        angles = np.arctan2(velocities[:, 1], velocities[:, 0])
        chaos = float(np.std(angles) / np.pi)   # normalize to 0-1
        return min(chaos, 1.0)

    def _compute_riot_risk(
        self, person_count: int, density_score: float, chaos: float, zone_violation: bool
    ) -> float:
        """Compute overall riot risk score 0.0–1.0"""
        # Normalize person count (20+ = max risk)
        count_score = min(person_count / 20.0, 1.0)

        zone_score = 1.0 if zone_violation else 0.0

        risk = (
            RIOT_RISK_WEIGHTS["person_count"]   * count_score +
            RIOT_RISK_WEIGHTS["density_score"]  * density_score +
            RIOT_RISK_WEIGHTS["movement_chaos"] * chaos +
            RIOT_RISK_WEIGHTS["zone_violation"] * zone_score
        )
        return round(min(risk, 1.0), 3)

    def analyze(
        self,
        frame: np.ndarray,
        person_detections: list[dict],
        restricted_zones: Optional[list[list]] = None,
    ) -> dict:
        """
        Full crowd analysis pipeline.

        Args:
            frame: BGR video frame
            person_detections: list of detection dicts with 'bbox' key
            restricted_zones: list of polygon points [[x,y], ...] for restricted areas

        Returns:
            Analysis result dict with annotated frame
        """
        h, w = frame.shape[:2]
        annotated = frame.copy()

        # Extract centroids from person detections
        centroids = []
        for det in person_detections:
            x1, y1, x2, y2 = det["bbox"]
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            centroids.append((cx, cy))

        person_count = len(centroids)
        crowd_level = self._get_crowd_level(person_count)

        # Update tracker
        tracks = self.tracker.update(centroids)

        # Density map
        density_map = self._compute_density_map(centroids, frame.shape)
        density_score = float(density_map.max())

        # Movement chaos
        chaos = self._compute_movement_chaos(tracks)

        # Zone violation check
        zone_violation = False
        if restricted_zones and centroids:
            for zone in restricted_zones:
                zone_poly = np.array(zone, dtype=np.int32)
                for cx, cy in centroids:
                    if cv2.pointPolygonTest(zone_poly, (cx, cy), False) >= 0:
                        zone_violation = True
                        break

        # Riot risk score
        riot_risk = self._compute_riot_risk(person_count, density_score, chaos, zone_violation)

        # Loitering detection
        loiterers = self.tracker.get_loiterers()

        # ── Annotate frame ────────────────────────────────────────────────────

        # Density heatmap overlay
        if person_count >= 3:
            heatmap_colored = cv2.applyColorMap(
                (density_map * 255).astype(np.uint8), cv2.COLORMAP_JET
            )
            heatmap_resized = cv2.resize(heatmap_colored, (w, h))
            annotated = cv2.addWeighted(annotated, 0.75, heatmap_resized, 0.25, 0)

        # Draw restricted zones
        if restricted_zones:
            for zone in restricted_zones:
                pts = np.array(zone, dtype=np.int32)
                cv2.polylines(annotated, [pts], True, (0, 0, 255), 2)
                cv2.fillPoly(
                    annotated,
                    [pts],
                    (0, 0, 255) if zone_violation else (0, 100, 255)
                )

        # Crowd stats panel (top-right)
        panel_x = w - 220
        cv2.rectangle(annotated, (panel_x, 0), (w, 130), (0, 0, 0), -1)
        cv2.rectangle(annotated, (panel_x, 0), (w, 130), (50, 50, 80), 1)

        level_colors = {
            "low": (0, 200, 0), "medium": (0, 200, 200),
            "high": (0, 100, 255), "critical": (0, 0, 255)
        }
        lc = level_colors.get(crowd_level, (200, 200, 200))

        cv2.putText(annotated, f"CROWD: {person_count} persons", (panel_x + 8, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, lc, 1)
        cv2.putText(annotated, f"Level: {crowd_level.upper()}", (panel_x + 8, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, lc, 1)
        cv2.putText(annotated, f"Riot Risk: {riot_risk:.0%}", (panel_x + 8, 62),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 0, 255) if riot_risk > 0.6 else (200, 200, 200), 1)
        cv2.putText(annotated, f"Chaos: {chaos:.0%}", (panel_x + 8, 82),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(annotated, f"Loitering: {len(loiterers)}", (panel_x + 8, 102),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Riot alert banner
        is_riot_alert = riot_risk > 0.65 or crowd_level == "critical"
        if is_riot_alert:
            cv2.rectangle(annotated, (0, h - 50), (w, h), (0, 0, 180), -1)
            cv2.putText(annotated, f"⚠ RIOT RISK: {riot_risk:.0%} — CROWD CONTROL REQUIRED",
                        (10, h - 18), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 2)

        return {
            "person_count": person_count,
            "crowd_level": crowd_level,
            "density_score": round(density_score, 3),
            "movement_chaos": round(chaos, 3),
            "riot_risk": riot_risk,
            "loiterer_count": len(loiterers),
            "zone_violation": zone_violation,
            "is_alert": is_riot_alert or len(loiterers) > 0 or zone_violation,
            "crime_type": "riot" if is_riot_alert else ("loitering" if loiterers else "suspicious"),
            "severity": "CRITICAL" if riot_risk > 0.8 else ("HIGH" if riot_risk > 0.5 else "MEDIUM"),
            "annotated_frame": annotated,
            "timestamp": datetime.utcnow().isoformat(),
        }

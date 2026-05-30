"""
CrimeWatch AI v2 — Demo Runner
Demonstrates ALL features: YOLO + Face + ANPR + Crowd + Night Vision + Audio

Usage:
  python simulation/demo_runner.py --source demo
  python simulation/demo_runner.py --source webcam
  python simulation/demo_runner.py --source video.mp4
  python simulation/demo_runner.py --source demo --scenario weapon
"""

import sys
import os
import cv2
import time
import argparse
import asyncio
import random
import math
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


def parse_args():
    p = argparse.ArgumentParser(description="CrimeWatch AI v2 Demo")
    p.add_argument("--source",     default="demo")
    p.add_argument("--camera-id",  default="CAM-DEMO")
    p.add_argument("--scenario",   default="all",
                   choices=["all", "fight", "weapon", "face", "anpr", "crowd", "night"])
    p.add_argument("--confidence", type=float, default=0.45)
    p.add_argument("--no-window",  action="store_true")
    return p.parse_args()


SCENARIO_SEQUENCE = [
    ("normal",         30, "All clear"),
    ("suspicious",     20, "Suspicious person detected"),
    ("normal",         20, "All clear"),
    ("fight",          25, "Fight detected — 2 persons"),
    ("normal",         20, "All clear"),
    ("weapon",         20, "Weapon detected — CRITICAL"),
    ("normal",         20, "All clear"),
    ("criminal",       20, "Criminal face match"),
    ("normal",         20, "All clear"),
    ("stolen_vehicle", 20, "Stolen vehicle detected"),
    ("normal",         20, "All clear"),
    ("riot",           25, "Riot risk — crowd of 15+"),
    ("normal",         30, "All clear"),
]


def make_synthetic_frame(scenario: str, frame_idx: int, w=1280, h=720) -> np.ndarray:
    """Generate a rich synthetic demo frame for the given scenario"""
    frame = np.zeros((h, w, 3), dtype=np.uint8)

    # Background gradient
    for y in range(h):
        v = int(10 + (y / h) * 12)
        frame[y, :] = [v, v + 4, v + 15]

    # Grid
    for x in range(0, w, 100):
        cv2.line(frame, (x, 0), (x, h), (18, 22, 38), 1)
    for y in range(0, h, 80):
        cv2.line(frame, (0, y), (w, y), (18, 22, 38), 1)

    t = frame_idx * 0.04
    color_map = {
        "normal":         (0, 180, 0),
        "suspicious":     (0, 200, 200),
        "fight":          (0, 80, 255),
        "weapon":         (0, 0, 255),
        "criminal":       (0, 0, 255),
        "stolen_vehicle": (0, 0, 255),
        "riot":           (0, 0, 200),
    }
    color = color_map.get(scenario, (0, 180, 0))

    if scenario == "normal":
        # Draw 1 person walking
        px = int(400 + 100 * math.sin(t * 0.5))
        py = int(350 + 20 * math.cos(t))
        _draw_person(frame, px, py, (0, 180, 0))

    elif scenario == "suspicious":
        px, py = int(900 + 10 * math.sin(t)), int(550 + 5 * math.cos(t))
        _draw_person(frame, px, py, color)
        cv2.putText(frame, "RESTRICTED ZONE", (750, 480),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 200), 1)
        cv2.rectangle(frame, (700, 490), (1100, 650), (0, 0, 200), 2)

    elif scenario == "fight":
        px1 = int(350 + 15 * math.sin(t * 2))
        px2 = int(430 + 15 * math.sin(t * 2 + 1))
        py = int(320 + 10 * math.cos(t))
        _draw_person(frame, px1, py, color)
        _draw_person(frame, px2, py, color)
        # Overlap indicator
        cv2.line(frame, (px1 + 20, py), (px2 - 20, py), (0, 0, 255), 2)
        cv2.putText(frame, "PROXIMITY ALERT", (350, py - 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    elif scenario == "weapon":
        px, py = int(400 + 10 * math.sin(t)), 320
        _draw_person(frame, px, py, color)
        # Knife
        cv2.rectangle(frame, (px + 25, py + 10), (px + 65, py + 22), (0, 0, 255), -1)
        cv2.rectangle(frame, (px + 20, py + 5), (px + 70, py + 27), (0, 0, 255), 2)
        cv2.putText(frame, "knife 0.91", (px + 20, py + 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)

    elif scenario == "criminal":
        px, py = int(400 + 8 * math.sin(t)), 300
        _draw_person(frame, px, py, (0, 0, 255))
        # Face box
        cv2.rectangle(frame, (px - 30, py - 90), (px + 30, py - 30), (0, 0, 255), 3)
        cv2.putText(frame, "⚠ CRIMINAL: Demo Suspect 001",
                    (px - 30, py - 98), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
        cv2.putText(frame, "Match: 87%", (px - 30, py - 115),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 100, 100), 1)

    elif scenario == "stolen_vehicle":
        # Car
        cv2.rectangle(frame, (150, 280), (700, 450), (0, 0, 255), 3)
        cv2.rectangle(frame, (200, 230), (650, 285), (0, 0, 255), 2)
        cv2.ellipse(frame, (250, 455), (50, 30), 0, 0, 360, (100, 100, 100), -1)
        cv2.ellipse(frame, (600, 455), (50, 30), 0, 0, 360, (100, 100, 100), -1)
        cv2.putText(frame, "car 0.94", (150, 275), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        # Plate
        cv2.rectangle(frame, (300, 420), (550, 450), (255, 255, 255), -1)
        cv2.putText(frame, "DL01AB1234", (310, 443),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.rectangle(frame, (150, 450), (700, 480), (0, 0, 0), -1)
        cv2.putText(frame, "DL01AB1234  [STOLEN — Honda City, White]",
                    (155, 472), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)

    elif scenario == "riot":
        # Draw 12 persons
        for i in range(12):
            angle = (i / 12) * 2 * math.pi + t * 0.3
            px = int(640 + 180 * math.cos(angle) + 15 * math.sin(t * 2 + i))
            py = int(360 + 100 * math.sin(angle) + 10 * math.cos(t + i))
            _draw_person(frame, px, py, color, small=True)
        cv2.putText(frame, "CROWD: 12 persons | Riot Risk: 78%",
                    (10, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

    # Alert banner
    if scenario != "normal":
        sev_map = {
            "weapon": "CRITICAL", "criminal": "CRITICAL", "riot": "CRITICAL",
            "fight": "HIGH", "stolen_vehicle": "HIGH", "suspicious": "MEDIUM",
        }
        sev = sev_map.get(scenario, "MEDIUM")
        banner_color = {"CRITICAL": (0, 0, 160), "HIGH": (0, 40, 160), "MEDIUM": (0, 80, 130)}[sev]
        cv2.rectangle(frame, (0, 0), (w, 52), banner_color, -1)
        cv2.putText(frame, f"  ⚠  {scenario.upper().replace('_', ' ')} DETECTED  |  {sev}",
                    (10, 36), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2)

    # HUD
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"CAM-DEMO  |  LIVE  |  {ts}",
                (10, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 100, 100), 1)
    cv2.putText(frame, f"FRAME {frame_idx:06d}",
                (w - 160, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)

    return frame


def _draw_person(frame, px, py, color, small=False):
    scale = 0.6 if small else 1.0
    r = int(18 * scale)
    cv2.ellipse(frame, (px, py - int(55 * scale)), (r, int(22 * scale)), 0, 0, 360, color, -1)
    cv2.rectangle(frame, (px - int(16 * scale), py - int(33 * scale)),
                  (px + int(16 * scale), py + int(35 * scale)), color, -1)
    cv2.line(frame, (px - int(16 * scale), py + int(35 * scale)),
             (px - int(22 * scale), py + int(80 * scale)), color, int(5 * scale))
    cv2.line(frame, (px + int(16 * scale), py + int(35 * scale)),
             (px + int(22 * scale), py + int(80 * scale)), color, int(5 * scale))
    if not small:
        cv2.rectangle(frame, (px - 35, py - 90), (px + 35, py + 85), color, 2)


async def run_demo(args):
    from dotenv import load_dotenv
    load_dotenv()

    print("\n" + "=" * 65)
    print("  🚨 CrimeWatch AI v2 — Full Feature Demo Runner")
    print("=" * 65)
    print(f"  Source:    {args.source}")
    print(f"  Scenario:  {args.scenario}")
    print(f"  Camera ID: {args.camera_id}")
    print("=" * 65)
    print("\n  Features active:")
    print("  ✓ YOLOv8 Object Detection")
    print("  ✓ Face Recognition + Criminal DB")
    print("  ✓ ANPR Number Plate Detection")
    print("  ✓ Crowd Density Analysis")
    print("  ✓ Night Vision Enhancement")
    print("  ✓ Crime Prediction AI")
    print("  ✓ Multi-channel Alerts (Telegram/WhatsApp/Email)")
    print("\n  Press 'q' to quit | 'n' for next scenario\n")

    from backend.ai.detector import CrimeDetector
    from backend.alerts.alert_manager import AlertManager

    detector = CrimeDetector(confidence=args.confidence)
    alert_mgr = AlertManager()

    use_synthetic = args.source in ("demo", "synthetic")
    cap = None

    if not use_synthetic:
        src = 0 if args.source == "webcam" else args.source
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            print(f"[WARN] Cannot open {args.source}, using synthetic demo")
            use_synthetic = True

    frame_idx = 0
    alert_count = 0
    scenario_idx = 0
    scenario_frame = 0
    start_time = time.time()

    try:
        while True:
            if use_synthetic:
                # Determine current scenario
                if args.scenario != "all":
                    current_scenario = args.scenario
                else:
                    sc_name, sc_duration, sc_desc = SCENARIO_SEQUENCE[scenario_idx % len(SCENARIO_SEQUENCE)]
                    current_scenario = sc_name
                    scenario_frame += 1
                    if scenario_frame >= sc_duration:
                        scenario_frame = 0
                        scenario_idx += 1
                        if scenario_idx < len(SCENARIO_SEQUENCE):
                            _, _, desc = SCENARIO_SEQUENCE[scenario_idx % len(SCENARIO_SEQUENCE)]
                            print(f"\n[SCENARIO] → {desc}")

                frame = make_synthetic_frame(current_scenario, frame_idx)
                time.sleep(0.05)
            else:
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue

            result = detector.detect_frame(frame, args.camera_id)
            frame_idx += 1

            if result["is_alert"]:
                alert_count += 1
                gps = {
                    "lat": 28.6139 + random.uniform(-0.02, 0.02),
                    "lng": 77.2090 + random.uniform(-0.02, 0.02),
                }
                await alert_mgr.dispatch(result, gps)

                extras = []
                if result.get("face", {}).get("has_criminal_match"):
                    names = [m["identity"] for m in result["face"]["criminal_matches"]]
                    extras.append(f"🦹 Criminal: {', '.join(names)}")
                if result.get("anpr", {}).get("has_alert"):
                    plates = [a.get("plate_text", "") for a in result["anpr"]["alerts"]]
                    extras.append(f"🚔 Plate: {', '.join(plates)}")
                if result.get("crowd", {}).get("riot_risk", 0) > 0.5:
                    extras.append(f"🚨 Riot Risk: {result['crowd']['riot_risk']:.0%}")
                if result.get("night_mode"):
                    extras.append("🌙 Night Mode")

                print(
                    f"[ALERT #{alert_count:03d}] "
                    f"{result['crime_type'].upper():16s} | "
                    f"{result['severity']:8s} | "
                    f"{result['confidence']:.0%} conf | "
                    f"{' | '.join(extras) if extras else ''}"
                )

            elif frame_idx % 50 == 0:
                elapsed = time.time() - start_time
                fps = frame_idx / elapsed
                print(f"[INFO] Frame {frame_idx:5d} | FPS: {fps:.1f} | NORMAL | Alerts: {alert_count}")

            if not args.no_window:
                cv2.imshow("CrimeWatch AI v2 — Demo (press Q to quit)", result["annotated_frame"])
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('n'):
                    scenario_idx += 1
                    scenario_frame = 0

    except KeyboardInterrupt:
        print("\n[INFO] Stopped by user")
    finally:
        if cap:
            cap.release()
        cv2.destroyAllWindows()
        elapsed = time.time() - start_time
        print(f"\n{'=' * 65}")
        print(f"  Demo Summary")
        print(f"{'=' * 65}")
        print(f"  Frames processed : {frame_idx}")
        print(f"  Total alerts     : {alert_count}")
        print(f"  Duration         : {elapsed:.1f}s")
        print(f"  Avg FPS          : {frame_idx / max(elapsed, 1):.1f}")
        print(f"{'=' * 65}\n")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(run_demo(args))

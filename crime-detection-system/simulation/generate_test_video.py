"""
Generate a synthetic test video for demo purposes.
Run this once to create a demo video file.

Usage: python simulation/generate_test_video.py
Output: simulation/demo_video.mp4
"""

import cv2
import numpy as np
import math
import random
from pathlib import Path
from datetime import datetime


def generate_demo_video(output_path: str = "simulation/demo_video.mp4", duration_sec: int = 30):
    width, height, fps = 1280, 720, 30
    total_frames = duration_sec * fps

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    print(f"Generating {duration_sec}s demo video ({total_frames} frames)...")

    scenarios = [
        ("normal",     0,   180),
        ("suspicious", 180, 360),
        ("normal",     360, 480),
        ("fight",      480, 600),
        ("normal",     600, 720),
        ("weapon",     720, 840),
        ("normal",     840, 900),
    ]

    for frame_idx in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Background
        for y in range(height):
            v = int(12 + (y / height) * 8)
            frame[y, :] = [v, v + 3, v + 12]

        # Grid
        for x in range(0, width, 100):
            cv2.line(frame, (x, 0), (x, height), (20, 25, 40), 1)
        for y in range(0, height, 80):
            cv2.line(frame, (0, y), (width, y), (20, 25, 40), 1)

        # Determine scenario
        crime_type = "normal"
        for ctype, start, end in scenarios:
            if start <= frame_idx < end:
                crime_type = ctype
                break

        t = frame_idx * 0.05
        color_map = {
            "normal":     (0, 180, 0),
            "suspicious": (0, 200, 200),
            "fight":      (0, 80, 255),
            "weapon":     (0, 0, 255),
        }
        color = color_map.get(crime_type, (0, 180, 0))

        # Draw persons
        num_persons = 2 if crime_type in ["fight", "weapon"] else 1
        for i in range(num_persons):
            px = int(350 + i * 200 + 40 * math.sin(t + i))
            py = int(350 + 20 * math.cos(t * 0.7 + i))

            # Person
            cv2.ellipse(frame, (px, py - 60), (18, 22), 0, 0, 360, color, -1)
            cv2.rectangle(frame, (px - 16, py - 38), (px + 16, py + 38), color, -1)
            cv2.line(frame, (px - 16, py + 38), (px - 22, py + 85), color, 5)
            cv2.line(frame, (px + 16, py + 38), (px + 22, py + 85), color, 5)

            # Bounding box
            cv2.rectangle(frame, (px - 32, py - 88), (px + 32, py + 90), color, 2)
            cv2.putText(frame, f"person {random.uniform(0.82, 0.96):.2f}",
                        (px - 32, py - 93), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

        # Weapon
        if crime_type == "weapon":
            cv2.rectangle(frame, (400, 340), (440, 350), (0, 0, 255), -1)
            cv2.putText(frame, "knife 0.91", (400, 335),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)

        # Alert banner
        if crime_type != "normal":
            cv2.rectangle(frame, (0, 0), (width, 52), (0, 0, 140), -1)
            cv2.putText(frame, f"  ALERT: {crime_type.upper()} DETECTED",
                        (10, 36), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2)

        # HUD
        ts = f"FRAME {frame_idx:05d}  |  {crime_type.upper()}"
        cv2.putText(frame, ts, (10, height - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 120, 120), 1)

        out.write(frame)

        if frame_idx % 150 == 0:
            print(f"  Progress: {frame_idx}/{total_frames} ({100*frame_idx//total_frames}%)")

    out.release()
    print(f"\n✓ Demo video saved: {output_path}")
    print(f"  Duration: {duration_sec}s | Resolution: {width}x{height} | FPS: {fps}")


if __name__ == "__main__":
    Path("simulation").mkdir(exist_ok=True)
    generate_demo_video()

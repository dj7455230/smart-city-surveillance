"""
CrimeWatch AI — Audio Crime Detection
Detects dangerous sounds: gunshots, screaming, glass breaking, explosions.

Uses Google's YAMNet model (via TensorFlow Hub) for audio classification.
Falls back to energy-based detection if TF not available.

Usage:
  detector = AudioDetector()
  detector.start_monitoring(callback=on_audio_alert)
"""

import os
import numpy as np
import logging
import asyncio
import threading
import time
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger("crimewatch.audio")

# YAMNet class indices for dangerous sounds (from AudioSet ontology)
DANGEROUS_SOUND_CLASSES = {
    # Gunshots / weapons
    "Gunshot, gunfire":         {"severity": "CRITICAL", "crime_type": "weapon"},
    "Machine gun":              {"severity": "CRITICAL", "crime_type": "weapon"},
    "Explosion":                {"severity": "CRITICAL", "crime_type": "explosion"},
    "Burst, pop":               {"severity": "HIGH",     "crime_type": "weapon"},

    # Violence
    "Screaming":                {"severity": "HIGH",     "crime_type": "fight"},
    "Crying, sobbing":          {"severity": "MEDIUM",   "crime_type": "suspicious"},
    "Fighting":                 {"severity": "HIGH",     "crime_type": "fight"},

    # Property crime
    "Glass":                    {"severity": "MEDIUM",   "crime_type": "suspicious"},
    "Breaking":                 {"severity": "MEDIUM",   "crime_type": "suspicious"},
    "Shatter":                  {"severity": "MEDIUM",   "crime_type": "suspicious"},

    # Accidents
    "Car alarm":                {"severity": "MEDIUM",   "crime_type": "accident"},
    "Crash":                    {"severity": "HIGH",     "crime_type": "accident"},
    "Tire squeal":              {"severity": "MEDIUM",   "crime_type": "accident"},
}

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.96   # YAMNet expects ~1s chunks
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION)


class AudioDetector:
    """
    Real-time audio crime detection using YAMNet.
    Runs in a background thread, calls callback on detection.
    """

    def __init__(self, device_index: Optional[int] = None, confidence_threshold: float = 0.5):
        self.device_index = device_index or int(os.getenv("AUDIO_DEVICE_INDEX", 0))
        self.confidence_threshold = confidence_threshold
        self.enabled = os.getenv("AUDIO_DETECTION_ENABLED", "false").lower() == "true"
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable] = None
        self._model = None
        self._class_names = None

    def _load_model(self) -> bool:
        """Load YAMNet from TensorFlow Hub"""
        try:
            import tensorflow as tf
            import tensorflow_hub as hub

            logger.info("[Audio] Loading YAMNet model...")
            self._model = hub.load("https://tfhub.dev/google/yamnet/1")

            # Load class names
            import csv
            import io
            import urllib.request
            url = "https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv"
            with urllib.request.urlopen(url) as response:
                reader = csv.DictReader(io.StringIO(response.read().decode()))
                self._class_names = [row["display_name"] for row in reader]

            logger.info("[Audio] YAMNet loaded ✓")
            return True

        except Exception as e:
            logger.warning(f"[Audio] YAMNet load failed: {e}. Using energy-based fallback.")
            return False

    def _classify_chunk(self, audio_chunk: np.ndarray) -> list[dict]:
        """Run YAMNet inference on audio chunk"""
        if self._model is None:
            return self._energy_based_detection(audio_chunk)

        try:
            import tensorflow as tf
            waveform = tf.constant(audio_chunk.astype(np.float32))
            scores, embeddings, spectrogram = self._model(waveform)
            scores_np = scores.numpy()

            # Average scores across time frames
            mean_scores = scores_np.mean(axis=0)

            detections = []
            for class_name, info in DANGEROUS_SOUND_CLASSES.items():
                if self._class_names and class_name in self._class_names:
                    idx = self._class_names.index(class_name)
                    if idx < len(mean_scores) and mean_scores[idx] > self.confidence_threshold:
                        detections.append({
                            "sound_class": class_name,
                            "confidence": float(mean_scores[idx]),
                            "severity": info["severity"],
                            "crime_type": info["crime_type"],
                        })

            return sorted(detections, key=lambda x: x["confidence"], reverse=True)

        except Exception as e:
            logger.debug(f"[Audio] Inference error: {e}")
            return []

    def _energy_based_detection(self, audio_chunk: np.ndarray) -> list[dict]:
        """
        Fallback: simple energy + zero-crossing rate analysis.
        Detects sudden loud sounds (gunshots, screams, crashes).
        """
        if len(audio_chunk) == 0:
            return []

        # RMS energy
        rms = np.sqrt(np.mean(audio_chunk ** 2))

        # Zero crossing rate (high for screams, low for gunshots)
        zcr = np.mean(np.abs(np.diff(np.sign(audio_chunk)))) / 2

        detections = []

        # Gunshot: very high energy, low ZCR, short duration
        if rms > 0.3 and zcr < 0.1:
            detections.append({
                "sound_class": "Gunshot (estimated)",
                "confidence": min(rms * 2, 0.95),
                "severity": "CRITICAL",
                "crime_type": "weapon",
            })

        # Scream: high energy, high ZCR
        elif rms > 0.15 and zcr > 0.3:
            detections.append({
                "sound_class": "Screaming (estimated)",
                "confidence": min(rms * 3, 0.85),
                "severity": "HIGH",
                "crime_type": "fight",
            })

        # Crash/explosion: very high energy spike
        elif rms > 0.4:
            detections.append({
                "sound_class": "Loud impact (estimated)",
                "confidence": min(rms * 1.5, 0.80),
                "severity": "HIGH",
                "crime_type": "accident",
            })

        return detections

    def _capture_and_detect(self):
        """Background thread: continuously capture audio and run detection"""
        try:
            import sounddevice as sd
        except ImportError:
            logger.warning("[Audio] sounddevice not installed. pip install sounddevice")
            return

        logger.info(f"[Audio] Starting microphone capture (device {self.device_index})")

        while self._running:
            try:
                audio_chunk = sd.rec(
                    CHUNK_SAMPLES,
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype=np.float32,
                    device=self.device_index,
                )
                sd.wait()
                audio_flat = audio_chunk.flatten()

                detections = self._classify_chunk(audio_flat)

                if detections and self._callback:
                    best = detections[0]
                    alert = {
                        "type": "AUDIO_ALERT",
                        "timestamp": datetime.utcnow().isoformat(),
                        "sound_class": best["sound_class"],
                        "confidence": best["confidence"],
                        "severity": best["severity"],
                        "crime_type": best["crime_type"],
                        "all_detections": detections,
                    }
                    logger.warning(f"[Audio] 🔊 {best['sound_class']} ({best['confidence']:.0%})")
                    asyncio.run_coroutine_threadsafe(
                        self._callback(alert),
                        asyncio.get_event_loop()
                    )

            except Exception as e:
                logger.debug(f"[Audio] Capture error: {e}")
                time.sleep(0.5)

    def start_monitoring(self, callback: Callable):
        """Start background audio monitoring"""
        if not self.enabled:
            logger.info("[Audio] Audio detection disabled (set AUDIO_DETECTION_ENABLED=true)")
            return

        self._callback = callback
        self._load_model()
        self._running = True
        self._thread = threading.Thread(target=self._capture_and_detect, daemon=True)
        self._thread.start()
        logger.info("[Audio] Monitoring started ✓")

    def stop_monitoring(self):
        """Stop background audio monitoring"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[Audio] Monitoring stopped")

    def analyze_file(self, audio_path: str) -> list[dict]:
        """Analyze an audio file (for testing/demo)"""
        try:
            import librosa
            audio, sr = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
            # Process in chunks
            all_detections = []
            for i in range(0, len(audio), CHUNK_SAMPLES):
                chunk = audio[i:i + CHUNK_SAMPLES]
                if len(chunk) < CHUNK_SAMPLES:
                    chunk = np.pad(chunk, (0, CHUNK_SAMPLES - len(chunk)))
                detections = self._classify_chunk(chunk)
                all_detections.extend(detections)
            return all_detections
        except Exception as e:
            logger.error(f"[Audio] File analysis error: {e}")
            return []

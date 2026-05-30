"""
CrimeWatch AI — Night Vision Enhancement
Enhances low-light video frames for better detection accuracy at night.

Techniques:
  1. CLAHE (Contrast Limited Adaptive Histogram Equalization) — fast, CPU
  2. Gamma correction — simple brightness boost
  3. Retinex-inspired enhancement — best quality
  4. Denoising — reduce noise in dark frames

Usage:
  enhancer = NightVisionEnhancer()
  enhanced_frame = enhancer.enhance(frame)
"""

import cv2
import numpy as np
import logging
from enum import Enum

logger = logging.getLogger("crimewatch.nightvision")


class EnhancementMode(str, Enum):
    AUTO    = "auto"      # Auto-detect if enhancement needed
    CLAHE   = "clahe"     # Fast, good for most cases
    GAMMA   = "gamma"     # Simple gamma correction
    RETINEX = "retinex"   # Best quality, slower
    NONE    = "none"      # Passthrough


class NightVisionEnhancer:
    """
    Enhances dark/low-light video frames for better AI detection.
    """

    def __init__(
        self,
        mode: EnhancementMode = EnhancementMode.AUTO,
        clahe_clip: float = 3.0,
        clahe_grid: tuple = (8, 8),
        gamma: float = 1.8,
        brightness_threshold: float = 60.0,  # mean brightness below this = night mode
    ):
        self.mode = mode
        self.clahe_clip = clahe_clip
        self.clahe_grid = clahe_grid
        self.gamma = gamma
        self.brightness_threshold = brightness_threshold

        # Pre-build CLAHE object (reuse for performance)
        self._clahe = cv2.createCLAHE(
            clipLimit=clahe_clip,
            tileGridSize=clahe_grid
        )

        # Pre-build gamma lookup table
        self._gamma_lut = self._build_gamma_lut(gamma)

    def _build_gamma_lut(self, gamma: float) -> np.ndarray:
        """Build gamma correction lookup table"""
        inv_gamma = 1.0 / gamma
        table = np.array([
            ((i / 255.0) ** inv_gamma) * 255
            for i in range(256)
        ], dtype=np.uint8)
        return table

    def _is_dark_frame(self, frame: np.ndarray) -> bool:
        """Check if frame needs enhancement based on mean brightness"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean_brightness = float(np.mean(gray))
        return mean_brightness < self.brightness_threshold

    def enhance_clahe(self, frame: np.ndarray) -> np.ndarray:
        """
        CLAHE enhancement — best balance of speed and quality.
        Works in LAB color space to preserve colors.
        """
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)

        # Apply CLAHE only to L (lightness) channel
        l_enhanced = self._clahe.apply(l)

        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        return enhanced

    def enhance_gamma(self, frame: np.ndarray) -> np.ndarray:
        """Simple gamma correction — fastest method"""
        return cv2.LUT(frame, self._gamma_lut)

    def enhance_retinex(self, frame: np.ndarray) -> np.ndarray:
        """
        Single-Scale Retinex (SSR) — best quality night enhancement.
        Inspired by human visual system's adaptation to low light.
        """
        frame_float = frame.astype(np.float32) + 1.0

        # Log domain processing
        log_frame = np.log(frame_float)

        # Gaussian blur (simulates illumination component)
        sigma = 80
        blurred = cv2.GaussianBlur(frame_float, (0, 0), sigma)
        log_blur = np.log(blurred + 1.0)

        # Retinex = log(image) - log(illumination)
        retinex = log_frame - log_blur

        # Normalize to 0-255
        retinex = retinex - retinex.min()
        if retinex.max() > 0:
            retinex = retinex / retinex.max() * 255

        enhanced = retinex.astype(np.uint8)

        # Blend with original for natural look
        enhanced = cv2.addWeighted(enhanced, 0.7, frame, 0.3, 0)
        return enhanced

    def denoise(self, frame: np.ndarray, strength: int = 7) -> np.ndarray:
        """Apply fast non-local means denoising"""
        return cv2.fastNlMeansDenoisingColored(frame, None, strength, strength, 7, 21)

    def enhance(self, frame: np.ndarray, force: bool = False) -> tuple[np.ndarray, bool]:
        """
        Main enhancement pipeline.

        Args:
            frame: Input BGR frame
            force: Force enhancement even if frame is bright

        Returns:
            (enhanced_frame, was_enhanced)
        """
        if self.mode == EnhancementMode.NONE:
            return frame, False

        # Auto mode: only enhance if dark
        if self.mode == EnhancementMode.AUTO and not force:
            if not self._is_dark_frame(frame):
                return frame, False

        # Apply selected enhancement
        if self.mode in (EnhancementMode.AUTO, EnhancementMode.CLAHE):
            enhanced = self.enhance_clahe(frame)
        elif self.mode == EnhancementMode.GAMMA:
            enhanced = self.enhance_gamma(frame)
        elif self.mode == EnhancementMode.RETINEX:
            enhanced = self.enhance_retinex(frame)
        else:
            enhanced = self.enhance_clahe(frame)

        # Add night vision overlay indicator
        cv2.putText(
            enhanced, "🌙 NIGHT MODE",
            (10, enhanced.shape[0] - 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 100), 1
        )

        return enhanced, True

    def create_side_by_side(self, original: np.ndarray, enhanced: np.ndarray) -> np.ndarray:
        """Create side-by-side comparison for demo"""
        h, w = original.shape[:2]
        combined = np.zeros((h, w * 2 + 4, 3), dtype=np.uint8)
        combined[:, :w] = original
        combined[:, w + 4:] = enhanced

        # Labels
        cv2.putText(combined, "ORIGINAL", (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        cv2.putText(combined, "NIGHT ENHANCED", (w + 14, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 100), 2)

        # Divider
        cv2.line(combined, (w + 2, 0), (w + 2, h), (100, 100, 100), 2)

        return combined

"""
Geliştirme modu kamera kaynağı: OpenCV VideoCapture ile yerel webcam.

Thread-safe okuma için lock kullanılır; aynı kameradan birden fazla istek
(ör. /video_feed akışı + bir status okuması) çakışmadan okuyabilsin.
"""
import threading
from typing import Optional

import cv2
import numpy as np

from .base import CameraSource


class WebcamSource(CameraSource):
    def __init__(
        self,
        index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 25,
    ) -> None:
        self._index = index
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()

    def open(self) -> None:
        with self._lock:
            if self._cap is not None and self._cap.isOpened():
                return
            cap = cv2.VideoCapture(self._index)
            import sys

        if sys.platform == "win32":
            # Windows: DirectShow backend'i USB kameralarda (or. Logitech Brio)
            # MSMF'e gore daha guvenilir acilir.
            cap = cv2.VideoCapture(self._index, cv2.CAP_DSHOW)
        else:
            # Mac (darwin) / Linux / Jetson: varsayilan backend.
            cap = cv2.VideoCapture(self._index)

        if not cap.isOpened():
            raise RuntimeError(
                f"Webcam açılamadı (index={self._index}). "
                f"Kamera bağlı mı ve başka bir uygulama tarafından "
                f"kullanılıyor olmadığından emin olun."
            )

        if sys.platform == "win32":
            # MJPG formatini SADECE Windows'ta iste. Mac dahili kameralari bu
            # formati desteklemez ve ayar kamerayi bozar; bu yuzden platforma ozel.
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, self._fps)
        self._cap = cap

    def read(self) -> Optional[np.ndarray]:
        with self._lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return frame

    def release(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None

    def is_opened(self) -> bool:
        with self._lock:
            return self._cap is not None and self._cap.isOpened()
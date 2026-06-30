"""
Saha modu kamera kaynağı: Hikrobot MV-CS050-60GC (GigE).

Bu fazda webcam ile geliştirildiği için fonksiyonel zorunlu DEĞİLDİR; ancak
arayüz (CameraSource) hazırdır ki saha moduna geçiş sadece config değişikliği
(CAMERA_SOURCE="hikrobot") ile mümkün olsun.

Bağlantı iki yoldan biriyle tamamlanabilir (Jetson/Ubuntu uyumlu):
  1. Hikrobot SDK (MVS / MvImport)  -> resmi SDK, ARM64 paketi mevcut.
  2. Açık kaynak GigE Vision (Aravis / GenICam-Harvester) -> tam açık kaynak.

İndirme: https://www.hikrobotics.com/en/machinevision/service/download/
"""
import threading
from typing import Optional

import numpy as np

from .base import CameraSource


class HikrobotSource(CameraSource):
    """
    Hikrobot GigE kamera iskeleti.

    NOT: Gerçek bağlantı henüz uygulanmadı (bu faz dışında). Metotlar arayüzü
    sağlar ama open() çağrıldığında bilinçli olarak NotImplementedError verir,
    böylece config yanlışlıkla "hikrobot"a ayarlanırsa sessizce bozuk
    çalışmaz, net bir hata mesajı verir.
    """

    def __init__(
        self,
        device_index: int = 0,
        ip: str = "",
        width: int = 1280,
        height: int = 720,
        fps: int = 25,
    ) -> None:
        self._device_index = device_index
        self._ip = ip
        self._width = width
        self._height = height
        self._fps = fps
        self._handle = None  # SDK cihaz tutamacı (camera handle)
        self._opened = False
        self._lock = threading.Lock()

    def open(self) -> None:
        # TODO: Hikrobot SDK (MvImport) veya Aravis/Harvester ile GigE bağlantısı.
        #
        # MvImport ile tipik akış:
        #   from MvCameraControl_class import MvCamera
        #   ... cihazları enumarate et (MV_GIGE_DEVICE) ...
        #   self._handle = MvCamera()
        #   self._handle.MV_CC_CreateHandle(device_info)
        #   self._handle.MV_CC_OpenDevice()
        #   # PixelFormat, ExposureTime, AcquisitionFrameRate ayarları (config'ten)
        #   self._handle.MV_CC_StartGrabbing()
        #
        # Aravis ile tipik akış:
        #   import gi; gi.require_version("Aravis", "0.8")
        #   from gi.repository import Aravis
        #   cam = Aravis.Camera.new(self._ip or None)
        #   cam.set_region(...); stream = cam.create_stream(); ...
        raise NotImplementedError(
            "Hikrobot saha modu bu fazda uygulanmadı. "
            "Geliştirme için CAMERA_SOURCE='webcam' kullanın. "
            "Saha entegrasyonu için Hikrobot SDK (MvImport) veya Aravis "
            "kurulup bu sınıfın gövdesi tamamlanmalıdır."
        )

    def read(self) -> Optional[np.ndarray]:
        # TODO: SDK'dan ham kareyi al (ör. MV_CC_GetImageBuffer), BGR'ye çevir
        #       (PixelFormat genelde BayerRG8/Mono8 -> cv2.cvtColor ile dönüştür)
        #       ve numpy ndarray döndür.
        with self._lock:
            if not self._opened:
                return None
        raise NotImplementedError("Hikrobot read() bu fazda uygulanmadı.")

    def release(self) -> None:
        # TODO: MV_CC_StopGrabbing -> MV_CC_CloseDevice -> MV_CC_DestroyHandle
        with self._lock:
            self._handle = None
            self._opened = False

    def is_opened(self) -> bool:
        with self._lock:
            return self._opened

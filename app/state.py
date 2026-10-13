"""
Çalışma zamanı durumu ve fabrika fonksiyonları.

Burada kamera kaynağı ve PLC istemcisi config'e göre SEÇİLİR; uygulamanın geri
kalanı somut sınıfları (webcam/hikrobot, mock/snap7) bilmez. Ayrıca PLC
sayacını arka planda yoklayan hafif bir thread ve canlı akış için kare üreten
mantık burada toplanır.

Model entegrasyonu (sonraki faz) için tek bir kanca noktası vardır:
`process_frame()` -> şu an kareyi olduğu gibi döndürür; ileride inference
burada çalışacaktır.
"""
from datetime import datetime
from pathlib import Path
import re
import threading
import time
from typing import Optional

import cv2
import numpy as np

from . import config
from .camera.base import CameraSource
from .plc.base import PLCClient


# ----------------------------------------------------------------------------
# Fabrikalar: config -> somut kaynak. Kaynak değiştirmek için SADECE config.
# ----------------------------------------------------------------------------
def create_camera() -> CameraSource:
    source = config.CAMERA_SOURCE.lower()
    if source == "webcam":
        from .camera.webcam import WebcamSource

        return WebcamSource(
            index=config.CAMERA_INDEX,
            width=config.FRAME_WIDTH,
            height=config.FRAME_HEIGHT,
            fps=config.TARGET_FPS,
        )
    if source == "hikrobot":
        from .camera.hikrobot import HikrobotSource

        return HikrobotSource(
            device_index=config.HIKROBOT_DEVICE_INDEX,
            ip=config.HIKROBOT_IP,
            width=config.FRAME_WIDTH,
            height=config.FRAME_HEIGHT,
            fps=config.TARGET_FPS,
        )
    raise ValueError(f"Bilinmeyen CAMERA_SOURCE: {config.CAMERA_SOURCE!r}")


def create_plc() -> PLCClient:
    if config.PLC_ENABLED:
        from .plc.snap7_client import Snap7Client

        return Snap7Client(
            ip=config.PLC_IP,
            rack=config.PLC_RACK,
            slot=config.PLC_SLOT,
            db_number=config.PLC_DB_NUMBER,
            counter_offset=config.PLC_COUNTER_OFFSET,
            line_running_timeout=config.LINE_RUNNING_TIMEOUT,
        )
    from .plc.mock import MockPLCClient

    return MockPLCClient(
        increment_interval=config.MOCK_PLC_INCREMENT_INTERVAL,
        line_running_timeout=config.LINE_RUNNING_TIMEOUT,
    )


class AppState:
    """
    Uygulamanın paylaşılan çalışma zamanı durumu.

    - Kamera başlat/durdur (operatör kontrolü)
    - PLC sayacını arka planda yoklayan thread
    - FPS ölçümü
    - MJPEG akışı için kare üretimi (hat durunca CPU yakmaz)
    """

    def __init__(self) -> None:
        self.camera: CameraSource = create_camera()
        self.plc: PLCClient = create_plc()

        # Operatör başlat/durdur durumu (kamera akışı aktif mi?)
        self._streaming = False
        self._state_lock = threading.Lock()

        # PLC yoklama thread'i
        self._capture_thread: Optional[threading.Thread] = None
        self._capture_stop = threading.Event()
        self._plc_thread: Optional[threading.Thread] = None
        self._plc_stop = threading.Event()
        self._counter: int = 0
        self._line_running: bool = False
        self._plc_connected: bool = False

        # FPS ölçümü (akış döngüsü tarafından güncellenir)
        self._fps: float = 0.0
        self._frame_times: list[float] = []

        # Son işlenen kare (hat durunca "beklemede" göstermek için)
        self._last_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
                # Otomatik kayıt durumu (arayüzden açılıp kapanır).
        self._auto_capture: bool = config.AUTO_CAPTURE_ENABLED
        # Otomatik kayıtta son kaydedilen sayaç değeri (aynı kutuyu iki kez
        # yazmamak için). None = henüz kayıt yapılmadı.
        self._last_saved_counter: Optional[int] = None
        # Toplam otomatik kaydedilen kare sayısı (arayüzde göstermek için).
        self._captured_count: int = 0

    # ----- yaşam döngüsü --------------------------------------------------
    def startup(self) -> None:
        """Uygulama açılışında: PLC'ye bağlan ve yoklama thread'ini başlat."""
        try:
            self.plc.connect()
            self._plc_connected = self.plc.is_connected()
        except Exception as exc:  # PLC yoksa uygulama yine de ayakta kalsın
            self._plc_connected = False
            print(f"[PLC] Bağlantı kurulamadı: {exc}")

        self._plc_stop.clear()
        self._plc_thread = threading.Thread(
            target=self._plc_poll_loop, name="plc-poll", daemon=True
        )
        self._plc_thread.start()

        self._capture_stop.clear()
        self._capture_thread = threading.Thread(
            target=self._capture_loop, name="capture", daemon=True
        )
        self._capture_thread.start()

    def shutdown(self) -> None:
        """Uygulama kapanışında: thread'i durdur, kaynakları serbest bırak."""
        self._capture_stop.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)
        self._plc_stop.set()
        if self._plc_thread is not None:
            self._plc_thread.join(timeout=2.0)
        self.stop_streaming()
        try:
            self.camera.release()
        except Exception:
            pass
        try:
            self.plc.disconnect()
        except Exception:
            pass

    # ----- PLC yoklama ----------------------------------------------------
    def _plc_poll_loop(self) -> None:
        while not self._plc_stop.is_set():
            try:
                if not self.plc.is_connected():
                    # Kopmus baglantiyi temiz durumdan tekrar kur
                    try:
                        self.plc.disconnect()
                    except Exception:
                        pass
                    self.plc.connect()
                value = self.plc.read_counter()
                if self._auto_capture and value != self._counter:
                    if self._last_saved_counter is not None:
                        saved = self.save_current_frame(config.CAPTURE_LABEL)
                        if saved is not None:
                            self._captured_count += 1
                    self._last_saved_counter = value
                self._counter = value
                self._line_running = self.plc.is_line_running()
                self._plc_connected = True
            except Exception as exc:
                self._plc_connected = False
                self._line_running = False
                print(f"[PLC] Hata, {config.PLC_RECONNECT_INTERVAL}s sonra tekrar denenecek: {exc}")
                self._plc_stop.wait(config.PLC_RECONNECT_INTERVAL)
                continue
            self._plc_stop.wait(config.PLC_POLL_INTERVAL)

    # ----- kamera başlat/durdur ------------------------------------------
    def start_streaming(self) -> None:
        with self._state_lock:
            if self._streaming:
                return
            self.camera.open()  # açılamazsa hata fırlatır
            self._streaming = True

    def stop_streaming(self) -> None:
        with self._state_lock:
            self._streaming = False
        # Not: kamera donanımını release() etmiyoruz ki tekrar başlat hızlı
        # olsun. Kamera donanımı shutdown()'da serbest bırakılır.

    @property
    def is_streaming(self) -> bool:
        with self._state_lock:
            return self._streaming

    # ----- model kancası (sonraki faz) -----------------------------------
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        # TODO: model inference (okey/not-okey) burada çalışacak.
        # Bu fazda kare olduğu gibi döndürülür. İleride:
        #   result = model.infer(frame)
        #   frame = draw_overlay(frame, result)  # işaretli kutu + etiket
        #   self._update_defect_stats(result)
        return frame
        # ----- kare kaydetme (otomatik + elle snapshot ortak) ----------------
    def save_current_frame(self, label: str) -> Optional[str]:
        """
        _last_frame'i data/<label>/ altına timestamp'li JPEG olarak yazar.
        Kaydedilen dosya yolunu döndürür; kare yoksa None döndürür.
        Hem otomatik kayıt hem elle snapshot bunu kullanır.
        """
        with self._frame_lock:
            frame = None if self._last_frame is None else self._last_frame.copy()
        if frame is None:
            return None
        out_dir = Path(config.CAPTURE_DIR) / label
        out_dir.mkdir(parents=True, exist_ok=True)
        # Artan isimlendirme: data1.jpg, data2.jpg, data3.jpg ...
        # Klasordeki mevcut en yuksek numarayi bulup bir fazlasini kullan
        # (uygulama yeniden baslasa da numaralandirma kaldigi yerden devam eder).
        max_n = 0
        for f in out_dir.glob("data*.jpg"):
            m = re.fullmatch(r"data(\d+)\.jpg", f.name)
            if m:
                max_n = max(max_n, int(m.group(1)))
        path = out_dir / f"data{max_n + 1:05d}.jpg"
        cv2.imwrite(
            str(path),
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), config.JPEG_QUALITY],
        )
        return str(path)
    def set_auto_capture(self, enabled: bool) -> None:
        """Otomatik kaydı aç/kapat. Kapatınca sayaç referansı sıfırlanır ki
        tekrar açıldığında ilk kutuda hemen kayıt yapılmasın."""
        self._auto_capture = enabled
        if not enabled:
            self._last_saved_counter = None
        # ----- kamera yakalama (producer) ------------------------------------
    def _capture_loop(self) -> None:
        """
        TEK yakalama thread'i. Kameradan okur, process_frame'den gecirir,
        sonucu _last_frame'e yazar. Kameraya dokunan yegane yer burasidir.
        Consumer'lar (mjpeg_frames) sadece _last_frame'i okur.
        """
        target_dt = 1.0 / max(1, config.TARGET_FPS)
        while not self._capture_stop.is_set():
            loop_start = time.monotonic()

            streaming = self.is_streaming
            active = streaming and (
                self._line_running or not config.REQUIRE_LINE_RUNNING
            )

            if active:
                frame = self.camera.read()
                if frame is not None:
                    frame = self.process_frame(frame)
                    with self._frame_lock:
                        self._last_frame = frame
                    self._record_frame_time()
                # kare alinamazsa _last_frame'e dokunma; consumer eski kareyi
                # veya placeholder'i gosterir.
                elapsed = time.monotonic() - loop_start
                sleep_for = target_dt - elapsed
                if sleep_for > 0:
                    self._capture_stop.wait(sleep_for)
            else:
                # Akis kapali veya hat durdu: kamera OKUNMAZ, CPU yakilmaz.
                self._fps = 0.0
                self._capture_stop.wait(0.2)
    # ----- FPS ------------------------------------------------------------
    def _record_frame_time(self) -> None:
        now = time.monotonic()
        self._frame_times.append(now)
        # Son 1 saniyelik pencere
        cutoff = now - 1.0
        while self._frame_times and self._frame_times[0] < cutoff:
            self._frame_times.pop(0)
        self._fps = float(len(self._frame_times))

    # ----- MJPEG kare üretimi --------------------------------------------
        # ----- MJPEG kare üretimi (consumer) ---------------------------------
    def mjpeg_frames(self):
        """
        multipart/x-mixed-replace icin JPEG kareler uretir (generator).

        Artik kameradan OKUMAZ. Yakalama thread'inin (_capture_loop) yazdigi
        _last_frame'i alir, JPEG'e cevirir, yollar. Her tarayici baglantisi
        ayri bir consumer'dir ama hepsi ayni _last_frame'i okur -> kamera
        izleyici sayisindan bagimsiz, tek kez okunur.
        """
        boundary = b"--frame"
        target_dt = 1.0 / max(1, config.TARGET_FPS)

        while True:
            streaming = self.is_streaming

            if streaming:
                with self._frame_lock:
                    src = None if self._last_frame is None else self._last_frame.copy()
                if src is not None:
                    frame = src
                else:
                    frame = self._placeholder_frame("KAMERA KARESI BEKLENIYOR")
                dt = target_dt
            else:
                # Akis durdurulmus: karartilmis idle karesi, dusuk hizda.
                frame = self._idle_frame()
                dt = 0.5

            ok, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), config.JPEG_QUALITY],
            )
            if ok:
                yield (
                    boundary
                    + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpeg)).encode()
                    + b"\r\n\r\n"
                    + jpeg.tobytes()
                    + b"\r\n"
                )

            time.sleep(dt)

        while True:
            loop_start = time.monotonic()
            streaming = self.is_streaming
            active = streaming and (self._line_running or not config.REQUIRE_LINE_RUNNING)
            # Ön çalışma: akış yalnızca Başlat/Durdur'a bağlı; PLC'ye bakmaz.
            # için buraya `and self._line_running` koşulu geri eklenecek.
            if active:
                frame = self.camera.read()
                if frame is not None:
                    frame = self.process_frame(frame)
                    self._last_frame = frame
                    self._record_frame_time()
                else:
                    frame = self._placeholder_frame("KAMERA KARESI ALINAMADI")
            else:
                # Akış durdurulmuş: kare işleme yok, CPU boşa yakılmaz.
                self._fps = 0.0
                frame = self._idle_frame()

            ok, jpeg = cv2.imencode(
                ".jpg",
                frame,
                [int(cv2.IMWRITE_JPEG_QUALITY), config.JPEG_QUALITY],
            )
            if ok:
                yield (
                    boundary
                    + b"\r\nContent-Type: image/jpeg\r\nContent-Length: "
                    + str(len(jpeg)).encode()
                    + b"\r\n\r\n"
                    + jpeg.tobytes()
                    + b"\r\n"
                )

            # Hız sınırlama: boştayken yavaş (CPU dostu), canlıyken hedef FPS.
            if streaming:
                elapsed = time.monotonic() - loop_start
                sleep_for = target_dt - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)
            else:
                time.sleep(0.5)  # boşta ~2 FPS, CPU yakmaz

    def _idle_frame(self) -> np.ndarray:
        """
        Boşta gösterilecek kare: sadece koyu/karartılmış bir görüntü döndürür.
        Mesaj METNİ buraya YAZILMAZ; bilgi yazısını HTML katmanı
        (#video-overlay) gösterir. Böylece kameranın üstünde iki yazının
        üst üste binmesi önlenir.
        """
        if self._last_frame is not None:
            base = self._last_frame.copy()
            base = (base * 0.30).astype(np.uint8)  # karart
        else:
            base = self._blank()
        return base

    def _placeholder_frame(self, message: str) -> np.ndarray:
        return self._draw_center_text(self._blank(), message)

    def _blank(self) -> np.ndarray:
        h = config.FRAME_HEIGHT
        w = config.FRAME_WIDTH
        img = np.zeros((h, w, 3), dtype=np.uint8)
        img[:] = (28, 28, 30)  # koyu gri
        return img

    @staticmethod
    def _draw_center_text(img: np.ndarray, text: str) -> np.ndarray:
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.2
        thickness = 2
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        x = (img.shape[1] - tw) // 2
        y = (img.shape[0] + th) // 2
        cv2.putText(img, text, (x, y), font, scale, (60, 200, 255), thickness,
                    cv2.LINE_AA)
        return img

    # ----- durum (status) -------------------------------------------------
    def last_frame(self) -> Optional[np.ndarray]:
        """Son islenen karenin kopyasini dondurur (yoksa None)."""
        frame = self._last_frame
        return None if frame is None else frame.copy()
    def status(self) -> dict:
        return {
            "streaming": self.is_streaming,
            "fps": round(self._fps, 1),
            "camera_connected": self._camera_connected(),
            "plc_connected": self._plc_connected,
            "counter": int(self._counter),
            "line_running": bool(self._line_running),
            "camera_source": config.CAMERA_SOURCE,
            "plc_mode": "snap7" if config.PLC_ENABLED else "mock",
            "auto_capture": bool(self._auto_capture),
            "captured_count": int(self._captured_count),
        }
    def _camera_connected(self) -> bool:
        try:
            return self.camera.is_opened()
        except Exception:
            return False

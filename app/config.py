"""
Uygulama yapılandırması.

Bağlantı parametreleri (kamera/PLC) koda gömülmez; buradan ya da ortam
değişkenlerinden (.env) okunur. Net olmayan PLC/kamera değerleri
`# TODO: otomasyon ekibinden alınacak` ile işaretlenmiştir.

Ortam değişkeni önceliklidir; örn:
    CAMERA_SOURCE=hikrobot PLC_ENABLED=true uvicorn app.main:app
"""
import os


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on", "evet")


# ----------------------------------------------------------------------------
# Kamera ayarları
# ----------------------------------------------------------------------------
# "webcam"  -> geliştirme (yerel kamera, cv2.VideoCapture)
# "hikrobot" -> saha (Hikrobot MV-CS050-60GC GigE) - iskelet hazır
CAMERA_SOURCE = _env_str("CAMERA_SOURCE", "webcam")

CAMERA_INDEX = _env_int("CAMERA_INDEX", 0)          # webcam cihaz indeksi
FRAME_WIDTH = _env_int("FRAME_WIDTH", 1280)
FRAME_HEIGHT = _env_int("FRAME_HEIGHT", 720)
TARGET_FPS = _env_int("TARGET_FPS", 25)             # akış hedef FPS
JPEG_QUALITY = _env_int("JPEG_QUALITY", 80)         # 1-100 MJPEG kalitesi

# Hikrobot (saha) - bu fazda webcam ile geliştirildiği için zorunlu değil.
# TODO: otomasyon ekibinden alınacak - kameranın IP / seri no bilgisi
HIKROBOT_DEVICE_INDEX = _env_int("HIKROBOT_DEVICE_INDEX", 0)
HIKROBOT_IP = _env_str("HIKROBOT_IP", "")           # TODO: doğru kamera IP'si

# ----------------------------------------------------------------------------
# PLC ayarları (Siemens S7-1500, python-snap7 ile okuma)
# ----------------------------------------------------------------------------
# Geliştirmede PLC olmadan çalışmak için False bırakın (mock sayaç kullanılır).
PLC_ENABLED = _env_bool("PLC_ENABLED", False)

PLC_IP = _env_str("PLC_IP", "192.168.0.1")          # TODO: otomasyon ekibinden alınacak
PLC_RACK = _env_int("PLC_RACK", 0)                  # tipik S7-1500: 0
PLC_SLOT = _env_int("PLC_SLOT", 1)                  # tipik S7-1500: 1
PLC_DB_NUMBER = _env_int("PLC_DB_NUMBER", 1)        # TODO: sayacın bulunduğu DB no
PLC_COUNTER_OFFSET = _env_int("PLC_COUNTER_OFFSET", 0)  # TODO: sayacın byte offset'i

# PLC'nin ne sıklıkla yoklanacağı (saniye)
PLC_POLL_INTERVAL = _env_float("PLC_POLL_INTERVAL", 0.5)
PLC_RECONNECT_INTERVAL = _env_float("PLC_RECONNECT_INTERVAL", 5.0)
# Hat "çalışıyor" kabul edilmesi için: sayaç son değişimden bu kadar saniye
# içinde değişmişse hat çalışıyor sayılır. Bu süre boyunca değişim yoksa
# hat "durdu" kabul edilir.
LINE_RUNNING_TIMEOUT = _env_float("LINE_RUNNING_TIMEOUT", 2.0)
REQUIRE_LINE_RUNNING = _env_bool("REQUIRE_LINE_RUNNING", False)

# ----------------------------------------------------------------------------
# Mock PLC ayarları (PLC_ENABLED=False iken kullanılır)
# ----------------------------------------------------------------------------
# Sahte sayacın artış aralığı (saniye). 0'dan büyükse hat hep "çalışıyor".
MOCK_PLC_INCREMENT_INTERVAL = _env_float("MOCK_PLC_INCREMENT_INTERVAL", 0.4)
# ----------------------------------------------------------------------------
# Otomatik kayıt (sayaç arttıkça kare kaydetme - veri toplama)
# ----------------------------------------------------------------------------
# True ise: PLC sayacı her arttığında o anki kare otomatik diske kaydedilir.
# Arayüzdeki "Görüntü kaydı" anahtarı bunu çalışma anında açıp kapatır;
# buradaki değer başlangıç durumudur.
AUTO_CAPTURE_ENABLED = _env_bool("AUTO_CAPTURE_ENABLED", False)

# Otomatik kaydedilen görüntülerin kök klasörü.
CAPTURE_DIR = _env_str("CAPTURE_DIR", "data")

# Otomatik kayıtlarda kullanılacak etiket alt klasörü (ör. data/dataset/...).
# Elle "okey/not okey" kayıtları ayrı klasörlere gider; otomatik toplama
# ham veri olduğu için nötr bir isim.
CAPTURE_LABEL = _env_str("CAPTURE_LABEL", "dataset")
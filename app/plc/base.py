"""
PLC istemci soyutlaması.

Backend yalnızca "hat durumu veren bir sinyal" görür; bunun gerçek bir
Siemens S7-1500 (snap7) mı yoksa sahte (mock) bir sayaç mı olduğunu bilmek
zorunda değildir. Bu sayede PLC olmadan da tüm akış test edilebilir.
"""
import threading
import time
from abc import ABC, abstractmethod


class PLCClient(ABC):
    """Tüm PLC istemcilerinin uyguladığı ortak arayüz."""

    @abstractmethod
    def connect(self) -> None:
        """PLC bağlantısını kur. Başarısızlıkta anlamlı hata fırlatır."""
        raise NotImplementedError

    @abstractmethod
    def read_counter(self) -> int:
        """Ürün sayacını (UInt32) oku ve döndür."""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        """Bağlantıyı kapat."""
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        """PLC'ye bağlı mı?"""
        raise NotImplementedError

    @abstractmethod
    def is_line_running(self) -> bool:
        """
        Hat çalışıyor mu? Genel yaklaşım: sayaç belirli bir zaman penceresi
        içinde değişiyorsa hat çalışıyor kabul edilir.
        """
        raise NotImplementedError


class _LineRunningMixin:
    """
    Sayaç değişimine göre "hat çalışıyor mu?" mantığını paylaşan yardımcı.

    `timeout` saniyesi içinde sayaç değeri en az bir kez değişmişse hat
    çalışıyor sayılır. read_counter()'ı çağıran istemciler her okumadan sonra
    `_note_counter(value)` çağırarak son değişim zamanını günceller.
    """

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout
        self._last_value: int | None = None
        self._last_change_ts: float = 0.0
        self._lock = threading.Lock()

    def _note_counter(self, value: int) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_value is None or value != self._last_value:
                self._last_value = value
                self._last_change_ts = now

    def _line_running(self) -> bool:
        with self._lock:
            if self._last_change_ts == 0.0:
                return False
            return (time.monotonic() - self._last_change_ts) <= self._timeout

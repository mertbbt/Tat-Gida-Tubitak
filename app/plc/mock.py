"""
Sahte (mock) PLC istemcisi.

PLC olmadan tüm akışın (kamera + arayüz + hat durumu mantığı) test
edilebilmesini sağlar. Belirli aralıkla artan bir sayaç üretir; böylece
arayüzde sayaç artışı ve "hat çalışıyor" rozeti gözlemlenebilir.

increment_interval <= 0 ise sayaç artmaz -> hat "durdu" olarak görünür
(durdurma davranışını test etmek için kullanışlıdır).
"""
import time

from .base import PLCClient, _LineRunningMixin


class MockPLCClient(PLCClient, _LineRunningMixin):
    def __init__(
        self,
        increment_interval: float,
        line_running_timeout: float,
        start_value: int = 0,
    ) -> None:
        _LineRunningMixin.__init__(self, timeout=line_running_timeout)
        self._increment_interval = increment_interval
        self._counter = start_value
        self._connected = False
        self._last_increment_ts = time.monotonic()

    def connect(self) -> None:
        self._connected = True
        self._last_increment_ts = time.monotonic()

    def read_counter(self) -> int:
        if self._increment_interval > 0:
            now = time.monotonic()
            elapsed = now - self._last_increment_ts
            if elapsed >= self._increment_interval:
                steps = int(elapsed // self._increment_interval)
                self._counter += steps
                self._last_increment_ts += steps * self._increment_interval
        self._note_counter(self._counter)
        return self._counter

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def is_line_running(self) -> bool:
        return self._line_running()

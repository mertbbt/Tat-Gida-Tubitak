"""
Gerçek PLC istemcisi: Siemens S7-1500'den python-snap7 ile UInt32 sayaç okuma.

ÖNEMLİ (otomasyon ekibiyle teyit edilecek, bkz. README Bölüm 4):
  * CPU Protection -> Connection mechanisms -> "Permit access with PUT/GET
    communication" ETKİN olmalı.
  * Okunacak DB için "Optimized block access" KAPALI olmalı (snap7 yalnızca
    mutlak byte adreslemeli / optimize olmayan bloklara erişir).

UInt32 okuma: DB'den 4 byte okunur ve big-endian DWORD olarak parse edilir.
"""
import struct
import threading

import snap7

from .base import PLCClient, _LineRunningMixin


class Snap7Client(PLCClient, _LineRunningMixin):
    def __init__(
        self,
        ip: str,
        rack: int,
        slot: int,
        db_number: int,
        counter_offset: int,
        line_running_timeout: float,
    ) -> None:
        _LineRunningMixin.__init__(self, timeout=line_running_timeout)
        self._ip = ip
        self._rack = rack
        self._slot = slot
        self._db_number = db_number
        self._counter_offset = counter_offset
        self._client = snap7.client.Client()
        self._conn_lock = threading.Lock()

    def connect(self) -> None:
        with self._conn_lock:
            if self._client.get_connected():
                return
            # Başarısızlıkta snap7 anlamlı bir exception fırlatır.
            self._client.connect(self._ip, self._rack, self._slot)
            if not self._client.get_connected():
                raise RuntimeError(
                    f"PLC bağlantısı kurulamadı: {self._ip} "
                    f"(rack={self._rack}, slot={self._slot}). "
                    f"PUT/GET izni ve ağ ayarlarını kontrol edin."
                )

    def read_counter(self) -> int:
        with self._conn_lock:
            data = self._client.db_read(self._db_number, self._counter_offset, 4)
        # Big-endian UInt32 (S7 DWORD)
        value = struct.unpack(">I", data)[0]
        self._note_counter(value)
        return value

    def disconnect(self) -> None:
        with self._conn_lock:
            try:
                if self._client.get_connected():
                    self._client.disconnect()
            finally:
                # destroy() bağlantı nesnesini tamamen serbest bırakır.
                try:
                    self._client.destroy()
                except Exception:
                    pass

    def is_connected(self) -> bool:
        with self._conn_lock:
            try:
                return bool(self._client.get_connected())
            except Exception:
                return False

    def is_line_running(self) -> bool:
        return self._line_running()

"""
Kamera kaynağı soyutlaması.

Backend yalnızca "kare üreten bir kaynak" görür; kaynağın webcam mi yoksa
Hikrobot GigE kamera mı olduğunu bilmek zorunda değildir. Yeni bir kamera
tipi eklemek için bu arayüzü uygulamak yeterlidir.
"""
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class CameraSource(ABC):
    """Tüm kamera kaynaklarının uyguladığı ortak arayüz."""

    @abstractmethod
    def open(self) -> None:
        """Kamerayı aç / bağlantı kur. Başarısızlıkta anlamlı hata fırlatır."""
        raise NotImplementedError

    @abstractmethod
    def read(self) -> Optional[np.ndarray]:
        """
        Tek bir kare döndürür (BGR, numpy ndarray).
        Kare alınamazsa None döndürür.
        """
        raise NotImplementedError

    @abstractmethod
    def release(self) -> None:
        """Kaynağı serbest bırak / bağlantıyı kapat."""
        raise NotImplementedError

    @abstractmethod
    def is_opened(self) -> bool:
        """Kamera şu an açık/bağlı mı?"""
        raise NotImplementedError

    # Context manager kolaylığı
    def __enter__(self) -> "CameraSource":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

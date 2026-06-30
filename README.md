# Konserve Kutu Kalite Kontrol — Canlı Görüntüleme Arayüzü (Faz 1)

TAT Gıda dolum hattında, dolum öncesi konserve kutularındaki hataların tespit
edilmesini amaçlayan projenin **ilk adımı**. Bu fazda **model/tespit yoktur**;
hedef canlı görüntü akışı, PLC sayaç okuma ve sonraki faza hazır temiz bir
proje iskeletidir.

> Hafta: 29 Haziran – 03 Temmuz. Akademik danışman: Doç. Dr. Yusuf Kuvvetli —
> Sanayi danışmanı: Çiğdem Şahin.

## Bu fazda ne var?

- Kameradan canlı görüntü (kamera kaynağı **soyutlanmış**: webcam ↔ Hikrobot).
- Görüntünün tarayıcıda gerçek zamanlı gösterimi (MJPEG over HTTP).
- Siemens S7-1500'den **UInt32 sayaç okuma** (gerçek snap7 ↔ mock, soyutlanmış).
- Hat yalnızca **çalışırken** (sayaç değişiyorken) kare işlenir; durunca CPU
  boşa yakılmaz.
- Sade, koyu, endüstriyel arayüz: canlı video, başlat/durdur, FPS, bağlantı
  durumu, sayaç ve "hat çalışıyor/durdu" rozeti.

Bu fazda **yapılmayanlar**: model/tespit, hatalı kutu ayırma, PLC'ye yazma,
veri toplama/etiketleme, yetkilendirme/veritabanı, Jetson'a fiili dağıtım.

## Hedef çalışma ortamı

- Sistem **Nvidia Jetson + Ubuntu (Linux/ARM64)** üzerinde çalışacaktır.
- Tüm bağımlılıklar Ubuntu/Jetson uyumludur; **Windows'a özel paket yoktur**.
- Python **3.10+** (python-snap7 ve modern OpenCV ile uyumlu).
- Geliştirme yerel makinede yapılabilir; mimari Jetson'a taşımayı
  kolaylaştıracak şekilde sade tutulmuştur.

## Kurulum

```bash
python3 -m venv venv
source venv/bin/activate          # Windows yok; Linux/macOS
pip install -r requirements.txt
```

## Çalıştırma

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Tarayıcıda: <http://localhost:8000>

Varsayılan ayarlarla (`CAMERA_SOURCE=webcam`, `PLC_ENABLED=false`):
canlı webcam görüntüsü + mock sayaç artışı + "hat çalışıyor" rozeti görünür.

## Yapılandırma

Tüm bağlantı parametreleri `app/config.py` içinde **ya da** ortam
değişkenleriyle ayarlanır (ortam değişkeni önceliklidir). Kaynak değiştirmek
**sadece config** ile yapılır; kod değişmez.

```bash
# Saha kamerasına geç (Hikrobot iskeleti — bkz. aşağıdaki not)
CAMERA_SOURCE=hikrobot uvicorn app.main:app

# Gerçek PLC'ye geç
PLC_ENABLED=true PLC_IP=192.168.0.10 PLC_DB_NUMBER=10 PLC_COUNTER_OFFSET=0 \
  uvicorn app.main:app
```

Öne çıkan ayarlar:

| Ayar | Açıklama |
|------|----------|
| `CAMERA_SOURCE` | `webcam` (geliştirme) / `hikrobot` (saha) |
| `CAMERA_INDEX`, `FRAME_WIDTH`, `FRAME_HEIGHT`, `TARGET_FPS`, `JPEG_QUALITY` | Kamera/akış |
| `PLC_ENABLED` | `false` → mock sayaç, `true` → gerçek snap7 |
| `PLC_IP`, `PLC_RACK`, `PLC_SLOT`, `PLC_DB_NUMBER`, `PLC_COUNTER_OFFSET` | S7-1500 bağlantısı |
| `PLC_POLL_INTERVAL`, `LINE_RUNNING_TIMEOUT` | Yoklama ve "hat çalışıyor" eşiği |

> Net olmayan PLC/kamera parametreleri `config.py` içinde `# TODO: otomasyon
> ekibinden alınacak` ile işaretlidir; varsayılan/placeholder değer verilmiştir.

## Mimari

Backend yalnızca **"kare üreten bir kaynak"** ve **"hat durumu veren bir
sinyal"** görür; bunların somut tipini bilmez.

```
app/
├── main.py            FastAPI route'ları + yaşam döngüsü
├── config.py          Tüm ayarlar (env override)
├── state.py           Çalışma zamanı durumu + kaynak fabrikaları + akış mantığı
├── camera/
│   ├── base.py        CameraSource soyut arayüzü
│   ├── webcam.py      OpenCV VideoCapture (geliştirme)
│   └── hikrobot.py    Hikrobot GigE iskeleti (saha) — TODO
└── plc/
    ├── base.py        PLCClient soyut arayüzü + "hat çalışıyor" mantığı
    ├── snap7_client.py  S7-1500 UInt32 okuma
    └── mock.py        Artan sahte sayaç (geliştirme)
```

- **Webcam ↔ Hikrobot** geçişi: `CAMERA_SOURCE`.
- **Mock ↔ gerçek snap7** geçişi: `PLC_ENABLED`.
- **Model kancası**: `app/state.py` içindeki `process_frame()`. Şu an kareyi
  olduğu gibi döndürür; sonraki fazda inference burada çalışacaktır
  (`# TODO: model inference`). Arayüzde de "Tespit (sonraki faz)" için boş yer
  tutucu alan bırakılmıştır.

## Endpoint'ler

| Yöntem | Yol | Açıklama |
|--------|-----|----------|
| GET | `/` | Arayüz |
| GET | `/video_feed` | MJPEG canlı akış |
| GET | `/status` | JSON: fps, camera_connected, plc_connected, counter, line_running |
| POST | `/camera/start` | Akışı başlat |
| POST | `/camera/stop` | Akışı durdur |

## Donanım ön koşulları (otomasyon ekibiyle teyit edilecek)

Bunlar **kod değildir**; PLC/kamera tarafının doğru ayarlanması gerekenlerdir.
Geliştirici bunları koda gömmez; bağlantı parametreleri config'ten okunur.

### Siemens S7-1500 (snap7 ile okuma için)

- **CPU Protection → Connection mechanisms → "Permit access with PUT/GET
  communication"** etkin olmalı.
- Okunacak Data Block için **"Optimized block access" KAPALI** olmalı (snap7
  yalnızca mutlak byte adreslemeli / optimize olmayan bloklara erişir).
- Gerekli parametreler: IP, rack, slot (tipik S7-1500: `rack=0, slot=1`), DB
  numarası, sayacın byte offset'i.
- Parametreler net değilse `config.py`'de `TODO` olarak işaretlidir; otomasyon
  ekibinden istenmelidir.

### Hikrobot MV-CS050-60GC (GigE)

- SDK: <https://www.hikrobotics.com/en/machinevision/service/download/>
  (yerel makineye/Jetson'a kurulacak).
- GigE kamera ile PC/Jetson **aynı alt ağda** olmalı; jumbo frame ve doğru NIC
  IP ayarı performans için önemlidir.
- Bu fazda fiziksel kamera yoksa **webcam** kaynağıyla geliştirilir; Hikrobot
  kaynağı arayüzü uygulanmış ama "saha modu" iskeleti olarak bırakılmıştır
  (`app/camera/hikrobot.py`).

## Teknoloji yığını

- **Backend:** Python + FastAPI + uvicorn (streaming/WebSocket dostu, Jetson
  uyumlu).
- **Görüntü:** OpenCV (`opencv-python`); Hikrobot için SDK (MvImport) veya
  Aravis/Harvester.
- **Akış:** MJPEG over HTTP (`multipart/x-mixed-replace`) — tarayıcıda `<img>`
  ile çalışır. Düşük gecikme gerekirse ileride WebRTC değerlendirilebilir.
- **PLC:** python-snap7 (saf Python, native bağımlılık yok → Jetson dostu).
- **Frontend:** tek sayfa HTML + CSS + vanilla JS.

## Başarı ölçütü (bu faz)

- [x] `localhost:8000`'de tarayıcıda canlı webcam görüntüsü akıyor.
- [x] Başlat / Durdur çalışıyor.
- [x] FPS ve bağlantı durumu arayüzde görünüyor.
- [x] Mock PLC ile sayaç ve "hat çalışıyor/durdu" durumu doğru güncelleniyor.
- [x] Hat "durdu" durumunda gereksiz kare işleme yapılmıyor.
- [x] Kaynaklar soyutlanmış: webcam↔Hikrobot, mock↔snap7 sadece config ile.
- [x] Tüm bağımlılıklar Ubuntu/Jetson uyumlu (Windows'a özel paket yok).
- [x] Kod, sonraki faz model entegrasyonu için temiz ayrılmış.

## Sonraki aşamalar (bu hafta yapılmayacak)

1. Hikrobot GigE saha modu (SDK/Aravis ile gerçek bağlantı, performans ayarı).
2. Veri toplama & etiketleme.
3. Model: CNN/YOLO tabanlı hata tespiti, Jetson'da gerçek zamanlı çıkarım.
4. PLC yazma / hatalı kutu ayırma.
5. Web arayüzü genişletme (canlı işaretleme, istatistik, geçmiş kayıt,
   yetkilendirme).

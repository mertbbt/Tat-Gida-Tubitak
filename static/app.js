// Ön çalışma: canlı kamera (gerçek) + başlat/durdur + kamera durumu/FPS.
// Kalite sonucu, sayaç, PLC ve yönetim bölümleri şimdilik STATİK/pasiftir;
// saha entegrasyonunda (PLC + Jetson modeli) devreye alınacaktır.

const POLL_MS = 1000;

// Ekranın köşesinde geçici bildirim gösterir.
// type: "ok" (yeşil) veya "err" (kırmızı)
function showToast(message, type = "ok") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  // Bir sonraki karede "show" ekle ki geçiş animasyonu çalışsın
  requestAnimationFrame(() => toast.classList.add("show"));

  // 3 saniye sonra soldur ve DOM'dan kaldır
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

const el = {
  overlay: document.getElementById("video-overlay"),
  btnStart: document.getElementById("btn-start"),
  btnStop: document.getElementById("btn-stop"),
  btnCapture: document.getElementById("btn-capture"),
  stFps: document.getElementById("st-fps"),
  stCamera: document.getElementById("st-camera"),
  connCamera: document.getElementById("conn-camera"),
  connCameraDot: document.getElementById("conn-camera-dot"),
};

async function postJson(url) {
  const res = await fetch(url, { method: "POST" });
  let data = {};
  try { data = await res.json(); } catch (_) {}
  return { ok: res.ok, data };
}

async function startStream() {
  el.btnStart.disabled = true;
  const { ok, data } = await postJson("/camera/start");
  if (!ok) {
    alert("Kamera başlatılamadı: " + (data.error || "bilinmeyen hata"));
    el.btnStart.disabled = false;
  }
}

async function stopStream() {
  el.btnStop.disabled = true;
  await postJson("/camera/stop");
}

function setValue(node, text, cls) {
  node.textContent = text;
  node.classList.remove("ok", "bad");
  if (cls) node.classList.add(cls);
}

function applyStatus(s) {
  setValue(el.stFps, String(s.fps));

  const camText = s.camera_connected ? "Bağlı" : (s.streaming ? "Hata" : "Kapalı");
  const camCls = s.camera_connected ? "ok" : (s.streaming ? "bad" : null);
  setValue(el.stCamera, camText, camCls);

  // Bağlantılar panelindeki kamera satırı
  el.connCamera.textContent = camText;
  el.connCamera.classList.toggle("off", !s.camera_connected);
  el.connCameraDot.className = s.camera_connected ? "dot-live" : "dot-off";

  el.btnStart.disabled = s.streaming;
  el.btnStop.disabled = !s.streaming;
  el.overlay.classList.toggle("hidden", s.streaming);
}

async function pollStatus() {
  try {
    const res = await fetch("/status");
    applyStatus(await res.json());
  } catch (_) {}
}

async function capturePhoto() {
  try {
    const res = await fetch(`/snapshot`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      showToast("Fotoğraf kaydedildi", "ok");
    } else {
      showToast(`Kaydedilemedi: ${data.detail || "bilinmeyen hata"}`, "err");
    }
  } catch (e) {
    showToast("Sunucuya ulaşılamadı", "err");
  }
}

el.btnStart.addEventListener("click", startStream);
el.btnStop.addEventListener("click", stopStream);
el.btnCapture.addEventListener("click", capturePhoto);

pollStatus();
setInterval(pollStatus, POLL_MS);
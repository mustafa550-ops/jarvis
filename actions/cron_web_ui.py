"""
Cron Web UI — Browser'dan zamanlanmış görev yönetimi.
OpenClaw'dan uyarlanmıştır.

Kullanım:
    from actions.cron_web_ui import CronWebServer
    server = CronWebServer(port=8765)
    server.start()  # Thread'de çalışır, blocking değil

    # Durdurmak için:
    server.stop()

URL: http://localhost:8765
"""

from __future__ import annotations

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from typing import Optional

from actions.system_cron import add_cron_job, list_cron_jobs, remove_cron_job, toggle_cron_job


HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🤖 JARVIS Cron Yönetimi</title>
<style>
  :root {
    --bg: #0a0a0f;
    --bg-card: #12121a;
    --bg-input: #1a1a2e;
    --border: #2a2a3e;
    --text: #e0e0e8;
    --text-muted: #8888a0;
    --primary: #00ff88;
    --primary-dark: #00cc6a;
    --danger: #ff4444;
    --warning: #ffaa00;
    --success: #00ff88;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.6;
  }
  h1 {
    font-size: 1.8rem;
    margin-bottom: 8px;
    background: linear-gradient(135deg, var(--primary), #4488ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .subtitle { color: var(--text-muted); margin-bottom: 24px; font-size: 0.9rem; }

  .card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 20px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }
  th {
    text-align: left;
    padding: 10px 8px;
    color: var(--primary);
    border-bottom: 2px solid var(--border);
    font-weight: 600;
  }
  td {
    padding: 10px 8px;
    border-bottom: 1px solid var(--border);
  }
  tr:hover td { background: rgba(0,255,136,0.03); }

  .status-enabled { color: var(--success); font-weight: 600; }
  .status-disabled { color: var(--danger); }

  .btn {
    padding: 6px 14px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    transition: opacity 0.2s;
  }
  .btn:hover { opacity: 0.8; }
  .btn-danger { background: var(--danger); color: white; }
  .btn-toggle { background: var(--warning); color: black; }
  .btn-primary { background: var(--primary); color: black; }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  @media (max-width: 600px) {
    .form-grid { grid-template-columns: 1fr; }
  }

  input, select {
    background: var(--bg-input);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 10px 12px;
    border-radius: 8px;
    font-size: 0.9rem;
    width: 100%;
  }
  input:focus, select:focus {
    outline: none;
    border-color: var(--primary);
  }

  .form-group { margin-bottom: 12px; }
  .form-group label {
    display: block;
    margin-bottom: 4px;
    color: var(--text-muted);
    font-size: 0.85rem;
  }

  .toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 0.9rem;
    animation: slideIn 0.3s ease;
    z-index: 1000;
  }
  .toast-success { background: var(--primary); color: black; }
  .toast-error { background: var(--danger); color: white; }

  @keyframes slideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }

  .empty-state {
    text-align: center;
    padding: 40px;
    color: var(--text-muted);
  }
  .empty-state svg {
    width: 64px;
    height: 64px;
    margin-bottom: 16px;
    opacity: 0.3;
  }
</style>
</head>
<body>
  <h1>🤖 JARVIS Cron Yönetimi</h1>
  <p class="subtitle">Zamanlanmış görevleri görüntüle, ekle, sil</p>

  <div class="card">
    <h2 style="margin-bottom: 16px; font-size: 1.1rem;">📋 Görevler</h2>
    <div id="jobsContainer">
      <div class="empty-state">
        <p>Yükleniyor...</p>
      </div>
    </div>
  </div>

  <div class="card">
    <h2 style="margin-bottom: 16px; font-size: 1.1rem;">➕ Yeni Görev</h2>
    <form id="newJobForm">
      <div class="form-grid">
        <div class="form-group">
          <label>Görev Adı</label>
          <input name="name" placeholder="örn: Sabah Disk Temizliği" required>
        </div>
        <div class="form-group">
          <label>Komut</label>
          <input name="command" placeholder="örn: temp_cleanup" required>
        </div>
        <div class="form-group">
          <label>Zamanlama Tipi</label>
          <select name="schedule_type">
            <option value="daily">Günlük</option>
            <option value="weekly">Haftalık</option>
            <option value="interval">Aralık (saniye)</option>
            <option value="once">Bir kere</option>
          </select>
        </div>
        <div class="form-group">
          <label>Zamanlama Değeri</label>
          <input name="schedule_value" placeholder="08:00 veya 3600" required>
        </div>
      </div>
      <button type="submit" class="btn btn-primary" style="margin-top: 12px; padding: 10px 24px;">
        ➕ Görev Ekle
      </button>
    </form>
  </div>

<script>
async function loadJobs() {
  const container = document.getElementById('jobsContainer');
  try {
    const res = await fetch('/api/jobs');
    const jobs = await res.json();

    if (jobs.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
          </svg>
          <p>Henüz görev yok. Yukarıdan yeni görev ekleyebilirsiniz.</p>
        </div>`;
      return;
    }

    const rows = jobs.map(j => `
      <tr>
        <td>${j.id}</td>
        <td><strong>${escapeHtml(j.name)}</strong></td>
        <td><code>${escapeHtml(j.command)}</code></td>
        <td>${j.schedule_type}</td>
        <td>${j.schedule_value}</td>
        <td>${formatDate(j.next_run)}</td>
        <td class="${j.enabled ? 'status-enabled' : 'status-disabled'}">
          ${j.enabled ? '✓ Aktif' : '✗ Pasif'}
        </td>
        <td>
          <button class="btn btn-toggle" onclick="toggleJob(${j.id}, ${!j.enabled})">
            ${j.enabled ? 'Durdur' : 'Başlat'}
          </button>
          <button class="btn btn-danger" onclick="deleteJob(${j.id})">Sil</button>
        </td>
      </tr>
    `).join('');

    container.innerHTML = `
      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Ad</th>
              <th>Komut</th>
              <th>Tip</th>
              <th>Değer</th>
              <th>Sonraki</th>
              <th>Durum</th>
              <th>İşlem</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  } catch (e) {
    container.innerHTML = `<div class="empty-state"><p>Hata: ${e.message}</p></div>`;
  }
}

async function deleteJob(id) {
  if (!confirm('Görev ' + id + ' silinsin mi?')) return;
  try {
    await fetch('/api/jobs/' + id, { method: 'DELETE' });
    showToast('Görev silindi', 'success');
    loadJobs();
  } catch (e) {
    showToast('Hata: ' + e.message, 'error');
  }
}

async function toggleJob(id, enabled) {
  try {
    await fetch('/api/jobs/' + id + '/toggle', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({enabled})
    });
    showToast(enabled ? 'Görev aktifleştirildi' : 'Görev durduruldu', 'success');
    loadJobs();
  } catch (e) {
    showToast('Hata: ' + e.message, 'error');
  }
}

document.getElementById('newJobForm').onsubmit = async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  const data = Object.fromEntries(form);

  try {
    const res = await fetch('/api/jobs', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    const result = await res.json();
    showToast(result.result || 'Görev eklendi', 'success');
    e.target.reset();
    loadJobs();
  } catch (e) {
    showToast('Hata: ' + e.message, 'error');
  }
};

function showToast(msg, type) {
  const toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatDate(iso) {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleString('tr-TR', {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
}

loadJobs();
setInterval(loadJobs, 10000);  // Her 10 saniyede yenile
</script>
</body>
</html>"""


class CronWebHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Cron Web UI."""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_html(HTML_DASHBOARD)
        elif path == "/api/jobs":
            self._handle_get_jobs()
        else:
            self._send_error(404, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/jobs":
            self._handle_create_job()
        elif path.startswith("/api/jobs/") and path.endswith("/toggle"):
            self._handle_toggle_job(path)
        else:
            self._send_error(404, "Not found")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/jobs/"):
            self._handle_delete_job(path)
        else:
            self._send_error(404, "Not found")

    def _handle_get_jobs(self):
        """Tüm görevleri JSON olarak döndür."""
        result = list_cron_jobs(enabled_only=False)

        # list_cron_jobs string döndürüyor, parse et
        # Basitçe SQLite'dan direkt okuyalım
        import sqlite3
        from actions.system_cron import DB_PATH

        conn = sqlite3.connect(str(DB_PATH))
        try:
            rows = conn.execute(
                "SELECT id, name, command, schedule_type, schedule_value, next_run, last_run, run_count, enabled FROM cron_jobs ORDER BY next_run"
            ).fetchall()

            jobs = []
            for row in rows:
                jobs.append({
                    "id": row[0],
                    "name": row[1],
                    "command": row[2],
                    "schedule_type": row[3],
                    "schedule_value": row[4],
                    "next_run": row[5],
                    "last_run": row[6],
                    "run_count": row[7],
                    "enabled": bool(row[8]),
                })

            self._send_json(jobs)
        finally:
            conn.close()

    def _handle_create_job(self):
        """Yeni görev oluştur."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')

        try:
            data = json.loads(post_data)
        except json.JSONDecodeError:
            data = parse_qs(post_data)
            data = {k: v[0] if v else "" for k, v in data.items()}

        result = add_cron_job(
            data.get("name", ""),
            data.get("command", ""),
            data.get("schedule_type", ""),
            data.get("schedule_value", ""),
        )

        self._send_json({"result": result})

    def _handle_delete_job(self, path: str):
        """Görev sil."""
        try:
            job_id = int(path.split("/")[-2])
            result = remove_cron_job(job_id)
            self._send_json({"result": result})
        except (ValueError, IndexError):
            self._send_error(400, "Invalid job ID")

    def _handle_toggle_job(self, path: str):
        """Görev durumunu değiştir."""
        try:
            job_id = int(path.split("/")[-2])
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data)

            result = toggle_cron_job(job_id, bool(data.get("enabled", True)))
            self._send_json({"result": result})
        except (ValueError, IndexError, json.JSONDecodeError):
            self._send_error(400, "Invalid request")

    def _send_html(self, html: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_error(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def log_message(self, format, *args):
        """Console spam'ini engelle."""
        pass


class CronWebServer:
    """
    Cron Web UI sunucusu.

    Thread'de çalışır, blocking değil.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> str:
        """Sunucuyu başlatır."""
        if self._running:
            return f"Sunucu zaten çalışıyor: http://{self.host}:{self.port}"

        try:
            self.server = HTTPServer((self.host, self.port), CronWebHandler)
            self._running = True
            self._thread = threading.Thread(target=self._serve, daemon=True, name="CronWebServer")
            self._thread.start()
            return f"Cron Web UI başlatıldı: http://{self.host}:{self.port}"
        except OSError as e:
            return f"Sunucu başlatma hatası: {e} (Port {self.port} kullanımda olabilir)"

    def _serve(self):
        """Ana sunucu döngüsü."""
        assert self.server is not None, "start() önce çağrılmalı"
        while self._running:
            try:
                self.server.handle_request()
            except Exception:
                break

    def stop(self) -> str:
        """Sunucuyu durdurur."""
        if not self._running:
            return "Sunucu zaten durdurulmuş."

        self._running = False
        if self.server:
            self.server.server_close()
        return "Cron Web UI durduruldu."

    def is_running(self) -> bool:
        return self._running


def start_cron_web_ui(port: int = 8765) -> str:
    """Hızlı başlatma fonksiyonu."""
    server = CronWebServer(port=port)
    return server.start()

"""Web UI/API for AI Translator OS.

Serves a dashboard and REST endpoints for translation, TTS, language
selection and status. Runs on Windows, Linux, macOS and Raspberry Pi.
"""

import io
import os
import threading
import time
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

try:
    from waitress import serve
    _HAS_WAITRESS = True
except Exception:
    _HAS_WAITRESS = False


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Translator OS</title>
  <link rel="icon" href="data:,">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 20px; background: #111; color: #eee; }
    h1 { color: #4f9; }
    .status { padding: 10px; border-radius: 6px; background: #222; margin-bottom: 15px; }
    .status span { font-weight: bold; color: #4f9; }
    .row { display: flex; gap: 10px; margin-bottom: 10px; flex-wrap: wrap; }
    select, input, button { padding: 10px; font-size: 1rem; border: 1px solid #555; background: #222; color: #eee; border-radius: 4px; }
    button { cursor: pointer; background: #2a4; border: none; }
    button:hover { background: #3c5; }
    #result { white-space: pre-wrap; background: #222; padding: 15px; border-radius: 6px; min-height: 80px; }
    #audioPlayer { width: 100%; margin-top: 10px; }
    .note { color: #888; font-size: 0.85rem; }
  </style>
</head>
<body>
  <h1>AI Translator OS v1.0</h1>
  <div class="status">สถานะ: <span id="statusText">-</span> | คู่ภาษา: <span id="langText">-</span></div>

  <div class="row">
    <select id="languageSelect"></select>
    <button onclick="setLanguage()">เปลี่ยนคู่ภาษา</button>
    <button onclick="refreshStatus()">รีเฟรช</button>
  </div>

  <h3>อุปกรณ์เสียง</h3>
  <div class="row">
    <select id="inputDevice"></select>
    <select id="outputDevice"></select>
    <button onclick="saveAudioDevices()">บันทึก</button>
    <button onclick="loadAudioDevices()">รีเฟรช</button>
  </div>

  <h3>แปลข้อความ</h3>
  <div class="row">
    <input type="text" id="textInput" placeholder="พิมพ์ข้อความ" style="flex:1">
    <button onclick="translateText()">แปล</button>
  </div>

  <h3>อัปโหลดเสียง</h3>
  <div class="row">
    <input type="file" id="audioInput" accept="audio/wav,audio/*">
    <button onclick="translateAudio()">แปลเสียง</button>
  </div>

  <h3>บันทึกเสียง (หยุดเมื่อเงียบ)</h3>
  <div class="row">
    <input type="number" id="recordDuration" value="10" min="1" max="30" style="width:60px">
    <span class="note" style="margin:auto 0">วินาทีสูงสุด</span>
    <button onclick="recordFromDevice()">🎤 พูดแล้วปล่อย</button>
  </div>

  <h3>TTS</h3>
  <div class="row">
    <input type="text" id="ttsInput" placeholder="ข้อความทีต้องการให้พูด" style="flex:1">
    <button onclick="speakTTS()">พูด</button>
  </div>

  <h3>ผลลัพธ์</h3>
  <div id="result"></div>
  <p class="note">Confidence ≥ 0.7 ถือว่าเชื่ือถือได้</p>

  <audio id="audioPlayer" controls style="display:none"></audio>

  <script>
    let languages = [];

    async function refreshStatus() {
      const r = await fetch('/api/status');
      const s = await r.json();
      document.getElementById('statusText').textContent = s.status || 'Unknown';
      document.getElementById('langText').textContent = `${s.language || '-'} (${s.language_key || ''})`;
      if (s.last_result) {
        document.getElementById('result').textContent = `ต้นฉบับ: ${s.last_result.source_text}\nแปล: ${s.last_result.translated}\nConfidence: ${s.last_result.confidence}`;
        if (s.last_result.tts_path) {
          loadAudio(s.last_result.tts_path);
        }
      }
    }

    async function loadLanguages() {
      const r = await fetch('/api/languages');
      const data = await r.json();
      languages = data.languages || [];
      const sel = document.getElementById('languageSelect');
      sel.innerHTML = '';
      languages.forEach(k => { const o = document.createElement('option'); o.value = k; o.textContent = k; sel.appendChild(o); });
    }

    async function loadAudioDevices() {
      const r = await fetch('/api/audio/devices');
      const data = await r.json();
      const inSel = document.getElementById('inputDevice');
      const outSel = document.getElementById('outputDevice');
      inSel.innerHTML = '';
      outSel.innerHTML = '';
      (data.input || []).forEach(d => { const o = document.createElement('option'); o.value = d.id; o.textContent = d.name; o.selected = (d.id === data.current_input); inSel.appendChild(o); });
      (data.output || []).forEach(d => { const o = document.createElement('option'); o.value = d.id; o.textContent = d.name; o.selected = (d.id === data.current_output); outSel.appendChild(o); });
    }

    async function saveAudioDevices() {
      const input = document.getElementById('inputDevice').value;
      const output = document.getElementById('outputDevice').value;
      await fetch('/api/audio/devices', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({input, output}) });
      await loadAudioDevices();
      await refreshStatus();
    }

    async function setLanguage() {
      const key = document.getElementById('languageSelect').value;
      await fetch('/api/language', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({key}) });
      await refreshStatus();
    }

    async function translateText() {
      const text = document.getElementById('textInput').value;
      const r = await fetch('/api/translate', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({text}) });
      const j = await r.json();
      showResult(j);
      if (j.tts_path) loadAudio(j.tts_path);
    }

    async function translateAudio() {
      const f = document.getElementById('audioInput').files[0];
      if (!f) return;
      const fd = new FormData(); fd.append('audio', f);
      const r = await fetch('/api/translate', { method: 'POST', body: fd });
      const j = await r.json();
      showResult(j);
      if (j.tts_path) loadAudio(j.tts_path);
    }

    async function speakTTS() {
      const text = document.getElementById('ttsInput').value;
      const r = await fetch('/api/tts', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({text}) });
      if (!r.ok) { const j = await r.json(); showResult(j); return; }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.getElementById('audioPlayer'); a.src = url; a.style.display = 'block'; a.play();
    }

    async function recordFromDevice() {
      const duration = parseInt(document.getElementById('recordDuration').value) || 10;
      const r = await fetch('/api/record', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({duration, use_vad: true}) });
      const s = await r.json();
      document.getElementById('statusText').textContent = s.status || 'Recording...';
    }

    function showResult(j) {
      if (j.error) { document.getElementById('result').textContent = 'ERROR: ' + j.error; return; }
      document.getElementById('result').textContent = `ต้นฉบับ: ${j.source_text}\nแปล: ${j.translated}\nConfidence: ${j.confidence} (${j.confident ? 'น่าเชื่ือถือ' : 'ต่ำ'})`;
    }

    function loadAudio(path) {
      const a = document.getElementById('audioPlayer'); a.src = '/api/tts?path=' + encodeURIComponent(path); a.style.display = 'block'; a.play();
    }

    loadLanguages();
    loadAudioDevices();
    refreshStatus();
    setInterval(refreshStatus, 2000);
  </script>
</body>
</html>"""


class WebServer:
    """Flask-based web UI/API for the translator."""

    def __init__(self, conv, host=None, port=None):
        self.conv = conv
        self.host = host or os.environ.get("WEB_HOST", "0.0.0.0")
        self.port = int(port or os.environ.get("WEB_PORT", "8080"))
        self.app = self._create_app()
        self._thread = None

    def _create_app(self):
        app = Flask(__name__)

        @app.route("/favicon.ico")
        def favicon():
            return "", 204

        @app.route("/")
        def index():
            return DASHBOARD_HTML

        @app.route("/api/status")
        def status():
            return jsonify(self.conv.get_status())

        @app.route("/api/languages")
        def languages():
            return jsonify({"languages": self.conv.packs_keys})

        @app.route("/api/language", methods=["POST"])
        def set_language():
            data = request.get_json(silent=True) or request.form.to_dict() or {}
            key = data.get("key")
            action = data.get("action")
            if key:
                self.conv.set_language_by_key(key)
            elif action == "next":
                self.conv.next_language()
            elif action == "prev":
                self.conv.previous_language()
            else:
                return jsonify({"error": "Provide key or action (next/prev)"}), 400
            return jsonify(self.conv.get_status())

        @app.route("/api/record", methods=["POST"])
        def record():
            data = request.get_json(silent=True) or {}
            duration = data.get("duration")
            use_vad = data.get("use_vad", False)
            try:
                if duration is not None:
                    duration = max(1, min(int(duration), 60))
            except (ValueError, TypeError):
                duration = None
            self.conv.start_listening(duration=duration, use_vad=use_vad)
            return jsonify(self.conv.get_status())

        @app.route("/api/audio/devices", methods=["GET"])
        def audio_devices():
            return jsonify({
                "input": self.conv.audio.list_input_devices(),
                "output": self.conv.audio.list_output_devices(),
                "current_input": self.conv.audio.device_input,
                "current_output": self.conv.audio.device_output,
            })

        @app.route("/api/audio/devices", methods=["POST"])
        def set_audio_devices():
            data = request.get_json(silent=True) or {}
            in_id = data.get("input")
            out_id = data.get("output")
            if in_id is not None:
                self.conv.audio.set_input_device(in_id)
            if out_id is not None:
                self.conv.audio.set_output_device(out_id)
            return jsonify({
                "ok": True,
                "current_input": self.conv.audio.device_input,
                "current_output": self.conv.audio.device_output,
            })

        @app.route("/api/translate", methods=["POST"])
        def translate():
            audio = request.files.get("audio")
            if audio:
                return self._translate_audio(audio)
            data = request.get_json(silent=True) or {}
            text = data.get("text", "")
            if not text:
                return jsonify({"error": "No text or audio provided"}), 400
            try:
                return jsonify(self.conv.translate_text(text))
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        @app.route("/api/tts", methods=["GET", "POST"])
        def tts():
            if request.method == "POST":
                data = request.get_json(silent=True) or {}
                text = data.get("text", "")
                voice = data.get("voice") or self.conv.tts._voice
            else:
                text = request.args.get("text", "")
                voice = request.args.get("voice") or self.conv.tts._voice
            if not text:
                return jsonify({"error": "No text provided"}), 400
            try:
                output = self.conv.tts.speak(text, voice=voice)
                path = Path(output)
                if not path.exists():
                    return jsonify({"error": "TTS did not produce a file"}), 500
                return send_file(path, mimetype="audio/wav")
            except Exception as exc:
                return jsonify({"error": str(exc)}), 500

        return app

    def _translate_audio(self, audio_file):
        """Save uploaded WAV, transcribe, then translate."""
        suffix = Path(audio_file.filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            audio_file.save(tmp)
            tmp_path = Path(tmp.name)

        try:
            whisper_lang = self.conv._whisper_lang(self.conv.source_lang)
            source_text = self.conv.speech.transcribe(tmp_path, language=whisper_lang)
            result = self.conv.translate_text(source_text)
            result["uploaded"] = str(tmp_path)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def start(self):
        """Start the web server in a background thread."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self):
        if _HAS_WAITRESS:
            serve(self.app, host=self.host, port=self.port)
        else:
            self.app.run(host=self.host, port=self.port, threaded=True)

    def stop(self):
        # Waitress does not expose a clean stop without more machinery.
        pass

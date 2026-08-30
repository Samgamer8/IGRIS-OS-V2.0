import os
import subprocess
import re
import threading
import base64
import queue
from pathlib import Path


POWERSHELL = "powershell.exe"


def _powershell_startupinfo() -> object | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    info.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return info


def _powershell_kwargs(**kwargs):
    hidden = _powershell_startupinfo()
    if hidden is None:
        return kwargs
    merged = dict(kwargs)
    merged.setdefault("startupinfo", hidden)
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        merged.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
    return merged


SPEAK = (
    "Add-Type -AssemblyName System.Speech;"
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$v=($s.GetInstalledVoices()|%{$_.VoiceInfo.Name}|?{$_ -match 'Pablo'}|Select-Object -First 1);"
    "if(-not $v){$v=($s.GetInstalledVoices()|%{$_.VoiceInfo.Name}|Select-Object -First 1)};"
    "if($v){$s.SelectVoice($v)};"
    "$s.Rate=-1;"
    "$s.Speak([Console]::In.ReadToEnd())")

SPEAK_ES = (
    "Add-Type -AssemblyName System.Speech;"
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$v=($s.GetInstalledVoices()|%{$_.VoiceInfo.Name}|?{$_ -match 'Pablo|Helena|Spanish|Español'}|Select-Object -First 1);"
    "if($v){$s.SelectVoice($v)};"
    "$s.Rate=-1;"
    "$s.Speak([Console]::In.ReadToEnd())")

LISTEN = (
    "Add-Type -AssemblyName System.Speech;"
    "$c=[Globalization.CultureInfo]::CurrentCulture;"
    "$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine($c);"
    "$r.SetInputToDefaultAudioDevice();"
    "$r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar));"
    "$x=$r.Recognize([TimeSpan]::FromSeconds(8));"
    "if($x){[Console]::OutputEncoding=[Text.Encoding]::UTF8;$x.Text}")


class WindowsVoice:
    _RESIDENT_SCRIPT = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$v=($s.GetInstalledVoices()|%{$_.VoiceInfo.Name}|?{$_ -match 'Pablo|Helena|Spanish|Español'}|Select-Object -First 1);"
        "if($v){$s.SelectVoice($v)};"
        "$s.Rate=-1;"
        "while($true){"
        "$line=[Console]::ReadLine();"
        "if(-not $line){break}"
        "if($line -eq 'EXIT'){break}"
        "if($line -match '^VOICE:(.+)$'){"
        "$name=$matches[1];"
        "$v=($s.GetInstalledVoices()|%{$_.VoiceInfo.Name}|?{$_ -eq $name}|Select-Object -First 1);"
        "if($v){$s.SelectVoice($v)}"
        "} elseif($line -match '^TEXT:(.+)$'){"
        "$bytes=[Convert]::FromBase64String($matches[1]);"
        "$text=[Text.Encoding]::UTF8.GetString($bytes);"
        "$s.Speak($text)"
        "}"
        "}")

    def __init__(self):
        self._resident = None
        self._current_voice_name = None
        self._speak_lock = threading.Lock()
        self._speech_queue: queue.Queue[tuple[str, str | None] | None] = queue.Queue(maxsize=1)
        self._speech_thread = threading.Thread(
            target=self._speech_worker, name="igris-tts", daemon=True)
        self._speech_thread.start()

    def __del__(self):
        self.close()

    def _ensure_resident(self):
        if self._resident is None or self._resident.poll() is not None:
            self._resident = subprocess.Popen(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', self._RESIDENT_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="ascii",
                **_powershell_kwargs(),
            )

    @staticmethod
    def get_installed_voices() -> list[str]:
        try:
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$s.GetInstalledVoices()|%{$_.VoiceInfo.Name}")
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True, text=True, timeout=10, check=False,
                **_powershell_kwargs(),
            )
            if result.returncode == 0:
                names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if names:
                    return names
        except Exception:
            pass
        return []

    def play_sample(self, path: Path) -> bool:
        if not path.is_file() or path.suffix.casefold() != ".wav":
            return False
        script = (
            "$p=$args[0];$s=New-Object Media.SoundPlayer $p;"
            "$s.PlaySync()")
        try:
            process = subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script,
                 str(path.resolve())], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **_powershell_kwargs())
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
            return True
        except OSError:
            return False

    def speak(self, text: str, voice_name: str | None = None) -> bool:
        clean_text = self._speech_text(text)
        if not clean_text:
            return False
        try:
            self._speech_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self._speech_queue.put_nowait((clean_text, voice_name))
            return True
        except queue.Full:
            return False

    def _speech_worker(self) -> None:
        while True:
            item = self._speech_queue.get()
            if item is None:
                return
            clean_text, voice_name = item
            with self._speak_lock:
                try:
                    self._ensure_resident()
                    if self._resident is None:
                        continue
                    if voice_name and voice_name != self._current_voice_name:
                        self._resident.stdin.write("VOICE:" + voice_name + "\n")
                        self._resident.stdin.flush()
                        self._current_voice_name = voice_name
                    encoded = base64.b64encode(
                        clean_text.encode("utf-8")).decode("ascii")
                    self._resident.stdin.write("TEXT:" + encoded + '\n')
                    self._resident.stdin.flush()
                except (OSError, ValueError):
                    self._resident = None

    @staticmethod
    def _speech_text(text: str) -> str:
        """Convierte la respuesta visual en una frase estable para TTS."""
        clean = re.sub(r"<[^>]+>", " ", str(text))
        clean = re.sub(r"\[[^\]]+\]", " ", clean)
        clean = re.sub(r"[`*_#]+", "", clean)
        clean = re.sub(r"%", " por ciento ", clean)
        clean = re.sub(r"[,/\\|<>+=~^:;'-]+", " ", clean)
        clean = re.sub(r"[^\w\s.?!¡¿]", " ", clean, flags=re.UNICODE)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:3000]

    def listen(self) -> str:
        try:
            run = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", LISTEN],
                capture_output=True, text=True, encoding="utf-8", timeout=12,
                **_powershell_kwargs())
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return run.stdout.strip() if run.returncode == 0 else ""

    def close(self):
        try:
            self._speech_queue.put_nowait(None)
            self._speech_thread.join(timeout=3)
        except (queue.Full, RuntimeError):
            pass
        if self._resident and self._resident.stdin:
            try:
                self._resident.stdin.write('EXIT\n')
                self._resident.stdin.flush()
            except (OSError, ValueError):
                pass
        if self._resident:
            try:
                self._resident.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._resident.kill()
                try:
                    self._resident.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
            self._resident = None

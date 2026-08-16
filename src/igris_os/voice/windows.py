import subprocess
from pathlib import Path


POWERSHELL = "powershell.exe"


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
        "while($true){"
        "$line=[Console]::ReadLine();"
        "if(-not $line){break}"
        "if($line -eq 'EXIT'){break}"
        "if($line -match '^VOICE:(.+)$'){"
        "$name=$matches[1];"
        "$v=($s.GetInstalledVoices()|%{$_.VoiceInfo.Name}|?{$_ -eq $name}|Select-Object -First 1);"
        "if($v){$s.SelectVoice($v)}"
        "} else {"
        "$s.Speak($line)"
        "}"
        "}")

    def __init__(self):
        self._resident = None
        self._current_voice_name = None

    def _ensure_resident(self):
        if self._resident is None or self._resident.poll() is not None:
            self._resident = subprocess.Popen(
                ['powershell.exe', '-NoProfile', '-Command', self._RESIDENT_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True
            )

    @staticmethod
    def get_installed_voices() -> list[str]:
        try:
            script = (
                "Add-Type -AssemblyName System.Speech;"
                "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                "$s.GetInstalledVoices()|%{$_.VoiceInfo.Name}")
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", script],
                capture_output=True, text=True, timeout=10, check=False,
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
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-Command", script,
                 str(path.resolve())], stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
            return True
        except OSError:
            return False

    def speak(self, text: str, voice_name: str | None = None) -> bool:
        if not text.strip():
            return False
        try:
            self._ensure_resident()
            if self._resident is None:
                return False
            if voice_name and voice_name != self._current_voice_name:
                self._resident.stdin.write("VOICE:" + voice_name + "\n")
                self._resident.stdin.flush()
                self._current_voice_name = voice_name
            self._resident.stdin.write(text + '\n')
            self._resident.stdin.flush()
            return True
        except (OSError, ValueError):
            self._resident = None
            return False

    def listen(self) -> str:
        try:
            run = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", LISTEN],
                capture_output=True, text=True, encoding="utf-8", timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return run.stdout.strip() if run.returncode == 0 else ""

    def close(self):
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

import subprocess


SPEAK = (
    "Add-Type -AssemblyName System.Speech;"
    "$t=[Console]::In.ReadToEnd();"
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
    "$s.Speak($t)")

LISTEN = (
    "Add-Type -AssemblyName System.Speech;"
    "$c=[Globalization.CultureInfo]::CurrentCulture;"
    "$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine($c);"
    "$r.SetInputToDefaultAudioDevice();"
    "$r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar));"
    "$x=$r.Recognize([TimeSpan]::FromSeconds(8));"
    "if($x){[Console]::OutputEncoding=[Text.Encoding]::UTF8;$x.Text}")


class WindowsVoice:
    def speak(self, text: str) -> bool:
        if not text.strip():
            return False
        try:
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-Command", SPEAK],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, text=True).communicate(text)
            return True
        except OSError:
            return False

    def listen(self) -> str:
        try:
            run = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", LISTEN],
                capture_output=True, text=True, encoding="utf-8", timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return run.stdout.strip() if run.returncode == 0 else ""

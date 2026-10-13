from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading

from .windows import WindowsVoice, _powershell_kwargs


# BLINDAJE 2026-10-13: el archivo assets/igris_voice_identity.wav es la voz
# personalizada de IGRIS. NO se toca, NO se sobrescribe, NO se regenera.
# Copia de seguridad: assets/igris_voice_identity_DO_NOT_TOUCH.wav
# (mismo tamaño, mismo contenido). Si este archivo cambia de tamaño o se
# pierde, el sistema avisa pero sigue usando el que haya.
_EXPECTED_VOICE_SIZE = 982158  # bytes, verificado 2026-10-13


class IdentityVoice(WindowsVoice):
    allow_fallback = False

    def __init__(self, reference: Path, runtime: Path, python: Path | None = None):
        self.reference = Path(reference).resolve()
        self.runtime = Path(runtime).resolve()
        self.python = python or Path(os.environ.get('IGRIS_VOICE_PYTHON') or
                         self.reference.parent.parent / '.venv-voice/Scripts/python.exe')
        self.events = queue.Queue()
        self._responses = queue.Queue()
        self._closed = threading.Event()
        # Caída: si la voz de referencia cuelga (problemas de CUDA en este HW),
        # se usa la voz de Windows (Microsoft Helena) para que la voz no se pierda.
        # FALLBACK ELIMINADO: nunca se usa Helena
        self._voice_errors = 0
        # Verificación de blindaje: la voz de IGRIS no debe cambiar de tamaño.
        try:
            actual = self.reference.stat().st_size
            if actual != _EXPECTED_VOICE_SIZE:
                self.events.put(
                    '[VOZ] AVISO: la voz de IGRIS (%s) mide %d bytes; se esperaban %d. '
                    'La voz personalizada puede no ser la original. '
                    'Conserva assets/igris_voice_identity_DO_NOT_TOUCH.wav como copia de seguridad.'
                    % (self.reference.name, actual, _EXPECTED_VOICE_SIZE))
        except OSError:
            pass
        super().__init__()

    def get_installed_voices(self) -> list[str]:
        return ['IGRIS - voz del WAV de referencia']

    def _ensure_resident(self):
        if self._resident is not None and self._resident.poll() is None:
            return
        if not Path(self.python).is_file():
            raise RuntimeError('Falta el entorno .venv-voice para Chatterbox')
        self.runtime.mkdir(parents=True, exist_ok=True)
        worker = Path(__file__).with_name('identity_worker.py')
        with (self.runtime / 'voice_identity.log').open('a', encoding='utf-8') as log:
            self._resident = subprocess.Popen(
                [str(self.python), '-u', str(worker)], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=log, text=True, encoding='utf-8',
                **_powershell_kwargs())
        self._responses = queue.Queue()
        threading.Thread(target=self._read_responses,
                         args=(self._resident, self._responses), daemon=True).start()

    @staticmethod
    def _read_responses(process, responses):
        try:
            for line in process.stdout:
                if line.startswith('IGRIS_VOICE:'):
                    responses.put(json.loads(line[len('IGRIS_VOICE:'):]))
        except (OSError, ValueError) as exc:
            responses.put({'ok': False, 'error': str(exc)})
        finally:
            responses.put({'ok': False, 'error': 'El proceso de voz se ha cerrado'})

    def _synthesize(self, text: str, output: Path) -> None:
        self._ensure_resident()
        request = {'text': text, 'reference': str(self.reference), 'output': str(output)}
        self._resident.stdin.write(json.dumps(request, ensure_ascii=True) + '\n')
        self._resident.stdin.flush()
        try:
            response = self._responses.get(timeout=45)
        except queue.Empty:
            self._resident.kill()
            self._resident.wait(timeout=5)
            raise RuntimeError('La generacion de voz excedio cuarenta y cinco segundos') from None
        if not response.get('ok'):
            raise RuntimeError(response.get('error', 'Fallo de sintesis'))
        if not output.is_file() or output.stat().st_size <= 44:
            raise RuntimeError('El motor no ha generado un WAV valido')

    def _play_response(self, text: str, directory: Path, play) -> None:
        # NO FALLBACK A HELENA / VOZ DE WINDOWS: la voz personalizada de IGRIS
        # (assets/igris_voice_identity.wav) es la única permitida.
        # Si falla, se reporta el error y NO se reproduce voz de sistema.
        if self._closed.is_set():
            return
        segments = self._speech_segments(text, limit=320)  # Frases más largas = menos síntesis
        if not segments:
            return
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix='igris-voice-prefetch') as executor:
            output = directory / 'speech_0.wav'
            pending = executor.submit(self._synthesize, segments[0], output)
            played = False
            for index in range(len(segments)):
                current = output
                try:
                    pending.result(timeout=45)
                    segment_ok = True
                except Exception as exc:
                    # Un fragmento fallido no silencia el resto de la respuesta:
                    # se reporta y se continua con el siguiente segmento.
                    segment_ok = False
                    self.events.put(
                        '[VOZ] Error de voz personalizada (NO se usa Helena): '
                        + str(exc) + '. Diagnostico: '
                        + str(self.runtime / 'voice_identity.log'))
                if self._closed.is_set():
                    return
                if index + 1 < len(segments):
                    output = directory / f'speech_{index + 1}.wav'
                    pending = executor.submit(self._synthesize, segments[index + 1], output)
                if segment_ok:
                    play(current)
                    played = True
            if not played and not self._closed.is_set():
                self.events.put('[VOZ] No se generó audio con la voz de IGRIS personalizada.')

    def _speech_worker(self) -> None:
        while not self._closed.is_set():
            item = self._speech_queue.get()
            if item is None or self._closed.is_set():
                return
            text, voice_name = item
            try:
                import winsound
                with self._speak_lock, tempfile.TemporaryDirectory(prefix='igris_voice_') as directory:
                    self._play_response(text, Path(directory),
                        lambda output: winsound.PlaySound(str(output), winsound.SND_FILENAME))
            except Exception as exc:
                self.events.put('No se pudo generar la voz de referencia: ' + str(exc)
                                + '. Diagnostico: ' + str(self.runtime / 'voice_identity.log'))


    def close(self):
        self._closed.set()
        if self._resident is not None:
            try:
                self._resident.terminate()
                self._resident.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                self._resident.kill()
            self._resident = None
        try:
            self._speech_queue.put_nowait(None)
        except queue.Full:
            pass
        if self._speech_thread is not threading.current_thread():
            self._speech_thread.join(timeout=3)
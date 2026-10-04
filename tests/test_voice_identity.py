from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import Mock, patch

from igris_os.voice.identity import IdentityVoice
from igris_os.voice.identity_worker import SPAIN_MODEL_REPOSITORY, load_spanish_model, synthesize


class VoiceIdentityTests(unittest.TestCase):
    def test_loader_uses_spain_checkpoint_and_matching_decoder(self):
        chatterbox = Mock()
        model = chatterbox.ChatterboxMultilingualTTS.from_pretrained.return_value
        model.s3gen.state_dict.return_value = {
            'tokenizer._mel_filters': 'computed mel filters', 'tokenizer.window': 'computed window'}
        hub = Mock()
        hub.hf_hub_download.side_effect = ['spain.safetensors', 'decoder.safetensors']
        tensors = Mock()
        tensors.load_file.side_effect = [{'t3': 'weights'}, {'decoder': 'weights'}]
        with patch.dict('sys.modules', {
            'chatterbox': Mock(), 'chatterbox.mtl_tts': chatterbox,
            'huggingface_hub': hub, 'safetensors': Mock(), 'safetensors.torch': tensors,
        }):
            self.assertIs(load_spanish_model('cuda'), model)
        self.assertEqual(hub.hf_hub_download.call_args_list[0].args, (SPAIN_MODEL_REPOSITORY,))
        self.assertEqual(hub.hf_hub_download.call_args_list[0].kwargs['filename'], 't3_es_es.safetensors')
        self.assertEqual(hub.hf_hub_download.call_args_list[1].kwargs['filename'], 's3gen_v3.safetensors')
        model.t3.load_state_dict.assert_called_once_with({'t3': 'weights'}, strict=True)
        model.s3gen.load_state_dict.assert_called_once_with({
            'decoder': 'weights', 'tokenizer._mel_filters': 'computed mel filters',
            'tokenizer.window': 'computed window'}, strict=True)

    def test_next_sentence_is_generated_during_playback_in_order(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            voice = IdentityVoice(root / 'assets/igris_voice_identity.wav', root / 'runtime')
            second_started = threading.Event()
            played = []

            def synthesize_segment(text, output):
                if text == 'Segunda frase.':
                    second_started.set()

            def play(output):
                if not played:
                    self.assertTrue(second_started.wait(timeout=2))
                played.append(output.name)

            try:
                with patch.object(voice, '_synthesize', side_effect=synthesize_segment):
                    voice._play_response('Primera frase. Segunda frase.', root, play)
                self.assertEqual(played, ['speech_0.wav', 'speech_1.wav'])
            finally:
                voice.close()

    def test_failed_generation_is_not_played(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            voice = IdentityVoice(root / 'assets/igris_voice_identity.wav', root / 'runtime')
            play = Mock()
            try:
                with patch.object(voice, '_synthesize', side_effect=RuntimeError('Fallo')):
                    voice._play_response('Primera frase.', root, play)
                play.assert_not_called()
                self.assertIn('No se pudo generar un fragmento de voz', voice.events.get_nowait())
            finally:
                voice.close()

    def test_segment_failure_does_not_abort_remaining_speech(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            voice = IdentityVoice(root / 'assets/igris_voice_identity.wav', root / 'runtime')
            played = []

            def synthesize_segment(text, output):
                if text == 'Primera frase.':
                    raise RuntimeError('semilla degenerada')

            def play(output):
                played.append(output.name)

            try:
                with patch.object(voice, '_synthesize', side_effect=synthesize_segment):
                    voice._play_response('Primera frase. Segunda frase.', root, play)
                # La primera frase falla y se omite, pero la segunda se reproduce
                # igualmente: un fragmento degenerado no silencia toda la respuesta.
                self.assertEqual(played, ['speech_1.wav'])
                self.assertIn('fragmento de voz', voice.events.get_nowait())
            finally:
                voice.close()

    def test_synthesis_uses_requested_reference_and_spanish(self):
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'igris_voice_identity.wav'
            reference.touch()
            output = Path(directory) / 'response.wav'
            model = Mock(sr=24000)
            samples = Mock(size=24000)
            model.generate.return_value.detach.return_value.cpu.return_value.numpy.return_value.reshape.return_value = samples
            soundfile = Mock()
            torch = Mock()
            torch.cuda.is_available.return_value = False
            with patch.dict('sys.modules', {'soundfile': soundfile, 'torch': torch}):
                synthesize(model, 'IGRIS preparado.', reference, output)
            torch.manual_seed.assert_called_once_with(42)
            model.prepare_conditionals.assert_called_once_with(str(reference.resolve()), exaggeration=0.5)
            model.generate.assert_called_once_with(
                'IGRIS preparado.', language_id='es',
                exaggeration=0.5, cfg_weight=0.5, temperature=0.8, repetition_penalty=1.2)
            soundfile.write.assert_called_once_with(str(output), samples, 24000, subtype='PCM_16')

    def test_reference_is_reused_until_the_file_changes(self):
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.touch()
            model = Mock(sr=24000)
            model.generate.return_value.detach.return_value.cpu.return_value.numpy.return_value.reshape.return_value = Mock(size=24000)
            with patch.dict('sys.modules', {'soundfile': Mock(), 'torch': Mock()}):
                synthesize(model, 'Primera frase.', reference, Path(directory) / 'first.wav')
                synthesize(model, 'Segunda frase.', reference, Path(directory) / 'second.wav')
                self.assertEqual(model.prepare_conditionals.call_count, 1)
                reference.write_bytes(b'updated reference')
                synthesize(model, 'Nueva referencia.', reference, Path(directory) / 'third.wav')
                self.assertEqual(model.prepare_conditionals.call_count, 2)

    def test_suspiciously_short_audio_is_retried_before_writing(self):
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.touch()
            model = Mock(sr=24000)
            short_audio = Mock()
            short_audio.detach.return_value.cpu.return_value.numpy.return_value.reshape.return_value = Mock(size=1200)
            full_audio = Mock()
            samples = Mock(size=240000)
            full_audio.detach.return_value.cpu.return_value.numpy.return_value.reshape.return_value = samples
            model.generate.side_effect = [short_audio, full_audio]
            soundfile = Mock()
            torch = Mock()
            with patch.dict('sys.modules', {'soundfile': soundfile, 'torch': torch}):
                synthesize(model, 'Una respuesta con varias palabras.', reference, Path(directory) / 'speech.wav')
            self.assertEqual(model.generate.call_count, 2)
            self.assertEqual([call.args[0] for call in torch.manual_seed.call_args_list], [42, 43])
            soundfile.write.assert_called_once()

    def test_repeated_short_audio_fails_with_bounded_retries(self):
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.touch()
            model = Mock(sr=24000)
            model.generate.return_value.detach.return_value.cpu.return_value.numpy.return_value.reshape.return_value = Mock(size=100)
            soundfile = Mock()
            with patch.dict('sys.modules', {'soundfile': soundfile, 'torch': Mock()}):
                with self.assertRaisesRegex(ValueError, 'demasiado corto'):
                    synthesize(model, 'Una respuesta con varias palabras.', reference, Path(directory) / 'speech.wav')
            self.assertEqual(model.generate.call_count, 4)
            soundfile.write.assert_not_called()

    def test_degenerate_seed_is_skipped_instead_of_failing_the_whole_request(self):
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.touch()
            model = Mock(sr=24000)
            full_audio = Mock()
            samples = Mock(size=240000)
            full_audio.detach.return_value.cpu.return_value.numpy.return_value.reshape.return_value = samples
            # La primera semilla reproduce el fallo real observado: un error
            # interno del modelo (p.ej. repeticion de token que fuerza un EOS
            # temprano y deja un tensor vacio), no audio corto.
            model.generate.side_effect = [
                RuntimeError("max(): Expected reduction dim 1 to have non-zero size."),
                full_audio,
            ]
            soundfile = Mock()
            with patch.dict('sys.modules', {'soundfile': soundfile, 'torch': Mock()}):
                synthesize(model, 'Una respuesta con varias palabras.', reference, Path(directory) / 'speech.wav')
            self.assertEqual(model.generate.call_count, 2)
            soundfile.write.assert_called_once()

    def test_all_seeds_degenerating_raises_with_last_error_context(self):
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.touch()
            model = Mock(sr=24000)
            model.generate.side_effect = RuntimeError(
                "max(): Expected reduction dim 1 to have non-zero size.")
            soundfile = Mock()
            with patch.dict('sys.modules', {'soundfile': soundfile, 'torch': Mock()}):
                with self.assertRaisesRegex(ValueError, 'todas las semillas'):
                    synthesize(model, 'Una respuesta con varias palabras.', reference, Path(directory) / 'speech.wav')
            self.assertEqual(model.generate.call_count, 4)
            soundfile.write.assert_not_called()

    def test_missing_reference_is_not_replaced_by_another_voice(self):
        model = Mock()
        with self.assertRaisesRegex(ValueError, 'referencia'):
            synthesize(model, 'Hola.', Path('missing.wav'), Path('output.wav'))
        model.generate.assert_not_called()

    def test_empty_text_is_rejected(self):
        with self.assertRaises(ValueError):
            synthesize(Mock(), ' ', Path('missing.wav'), Path('output.wav'))

    def test_identity_backend_does_not_allow_windows_fallback(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            voice = IdentityVoice(root / 'assets/igris_voice_identity.wav', root / 'runtime')
            try:
                self.assertFalse(voice.allow_fallback)
                self.assertEqual(voice.python, root / '.venv-voice/Scripts/python.exe')
                with self.assertRaisesRegex(RuntimeError, 'entorno'):
                    voice._ensure_resident()
            finally:
                voice.close()

    def test_worker_failure_is_reported_without_another_voice(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            voice = IdentityVoice(root / 'assets/igris_voice_identity.wav', root / 'runtime')
            try:
                voice._resident = Mock()
                voice._responses.put({'ok': False, 'error': 'GPU sin memoria'})
                with patch.object(voice, '_ensure_resident'):
                    with self.assertRaisesRegex(RuntimeError, 'GPU sin memoria'):
                        voice._synthesize('Hola.', root / 'speech.wav')
                request = voice._resident.stdin.write.call_args.args[0]
                self.assertIn('igris_voice_identity.wav', request)
            finally:
                voice.close()


if __name__ == '__main__':
    unittest.main()
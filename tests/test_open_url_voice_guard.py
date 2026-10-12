import unittest
from unittest.mock import Mock, patch

from igris_os.application.assistant import AssistantService
from igris_os.capabilities.host import open_url
from igris_os.voice.windows import WindowsVoice


class TestHostOpenUrl(unittest.TestCase):
    def test_rejects_non_github_url(self):
        result = open_url({"url": "https://evil.example/phish"})
        self.assertFalse(result.ok)

    def test_rejects_non_https(self):
        result = open_url({"url": "http://github.com/o/r"})
        self.assertFalse(result.ok)

    def test_rejects_empty(self):
        result = open_url({})
        self.assertFalse(result.ok)

    def test_accepts_github_https(self):
        with patch("igris_os.capabilities.host.os") as mock_os:
            mock_os.name = "nt"
            result = open_url({"url": "https://github.com/langchain-ai/langchain"})
        self.assertTrue(result.ok)
        mock_os.startfile.assert_called_once_with("https://github.com/langchain-ai/langchain")


class TestNoInventedRepoLists(unittest.TestCase):
    def test_conversation_prompt_bans_invented_repos(self):
        prompt = AssistantService._conversation_prompt("repos de agentes", ())
        self.assertIn("No inventes listas de repositorios", prompt)

    def test_conversation_prompt_requires_full_sentences(self):
        prompt = AssistantService._conversation_prompt("repos de agentes", ())
        self.assertIn("frases completas", prompt)


class TestSpeechSegmentsSkipOneWordFragments(unittest.TestCase):
    def _segments(self, text):
        return WindowsVoice._speech_segments(WindowsVoice._speech_text(text), limit=320)

    def test_markdown_list_names_do_not_produce_orphan_words(self):
        text = "1. **LangChain**: un framework. 2. **MindsDB**: una plataforma."
        segments = self._segments(text)
        for segment in segments:
            self.assertGreaterEqual(len(segment.split()), 2, segment)

    def test_short_notices_still_speak(self):
        segments = self._segments("Hola. Soy IGRIS OS, tu asistente local.")
        self.assertTrue(segments)
        # Ninguna palabra se pierde ni se reescribe: el audio dice lo mismo,
        # solo que sin fragmentos huerfanos que colapsen la sintesis.
        # (El saneador previo ya elimina la coma; comportamiento preexistente.)
        self.assertEqual(" ".join(segments),
                         "Hola. Soy IGRIS OS tu asistente local.")


if __name__ == "__main__":
    unittest.main()

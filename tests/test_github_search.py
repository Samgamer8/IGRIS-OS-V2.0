"""Tests de la busqueda real de repositorios en GitHub.

La API de GitHub y el lanzamiento de Chrome se mockean: ningun test abre
ventanas reales ni consume la cuota de GitHub. Verifica que los datos son
reales (conteo + orden por estrellas), que los errores se reportan sin
inventar, y que se abren 5 ventanas independientes.
"""
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from igris_os.capabilities import github_search
from igris_os.capabilities.github_search import (
    RepoHit, RepoSearchResult, extract_github_query, format_report,
    search_and_open, search_repositories,
)


def _fake_api_payload():
    return {
        "total_count": 3592,
        "items": [
            {"full_name": f"org/repo{i}", "stargazers_count": 100 - i,
             "html_url": f"https://github.com/org/repo{i}",
             "description": f"desc {i}", "language": "Python",
             "license": {"spdx_id": "MIT"}}
            for i in range(8)
        ],
    }


class TestQueryExtraction(unittest.TestCase):
    def test_removes_filler_and_translates(self):
        query = extract_github_query(
            "puedes buscar en la pagina de github.com repositorios de "
            "aplicaciones de IA que englovan multiples agentes de forma free")
        self.assertIn("agent", query)
        self.assertIn("AI", query)
        self.assertIn("multi", query)
        for filler in ("github", "buscar", "repositorios", "forma", "free"):
            self.assertNotIn(filler, query.split())

    def test_empty_when_only_filler(self):
        self.assertEqual(extract_github_query("busca en github repositorios"), "")


class TestSearchRepositories(unittest.TestCase):
    @patch.object(github_search, "_get_json", return_value=_fake_api_payload())
    def test_parses_count_and_ranks_by_stars(self, _mock):
        result = search_repositories("multi agent AI", top_n=5)
        self.assertEqual(result.total_count, 3592)
        self.assertEqual(len(result.hits), 5)
        stars = [hit.stars for hit in result.hits]
        self.assertEqual(stars, sorted(stars, reverse=True))
        self.assertEqual(result.hits[0].url, "https://github.com/org/repo0")
        self.assertEqual(result.hits[0].license, "MIT")

    @patch.object(github_search, "_get_json",
                  side_effect=HTTPError(None, 403, "rate limit", None, None))
    def test_rate_limit_is_reported_not_invented(self, _mock):
        result = search_repositories("anything")
        self.assertTrue(result.rate_limited)
        self.assertEqual(result.total_count, 0)
        self.assertIn("token", result.error.lower())

    @patch.object(github_search, "_get_json", side_effect=OSError("sin red"))
    def test_network_error_is_reported(self, _mock):
        result = search_repositories("anything")
        self.assertEqual(result.hits, ())
        self.assertIn("GitHub", result.error)

    def test_empty_query_short_circuits(self):
        result = search_repositories("   ")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.error, "Consulta vacia.")


class TestSearchAndOpen(unittest.TestCase):
    @patch.object(github_search, "_get_json", return_value=_fake_api_payload())
    def test_opens_top_five_independent_windows(self, _mock):
        opened = []

        def fake_opener(url):
            opened.append(url)
            return True

        _result, opened_urls = search_and_open("multi agent", top_n=5,
                                               opener=fake_opener)
        self.assertEqual(len(opened_urls), 5)
        self.assertEqual(opened, opened_urls)
        self.assertEqual(opened_urls[0], "https://github.com/org/repo0")

    @patch.object(github_search, "_get_json", return_value=_fake_api_payload())
    def test_opener_failure_does_not_break_search(self, _mock):
        result, opened_urls = search_and_open("multi agent", top_n=5,
                                              opener=lambda url: False)
        self.assertEqual(result.total_count, 3592)
        self.assertEqual(opened_urls, [])


class TestFormatReport(unittest.TestCase):
    def test_report_uses_real_count_and_lists_top(self):
        result = RepoSearchResult(
            query="multi agent AI", total_count=3592,
            hits=(RepoHit("org/a", 100, "https://github.com/org/a", "d",
                          "Python", "MIT"),))
        report = format_report(result, ["https://github.com/org/a"])
        self.assertIn("3592", report)
        self.assertIn("org/a", report)
        self.assertIn("100 estrellas", report)
        self.assertIn("He abierto", report)

    def test_report_no_results(self):
        result = RepoSearchResult(query="xyz", total_count=0, hits=())
        self.assertIn("No encontre", format_report(result, []))


class TestOpenChromeWindow(unittest.TestCase):
    def test_rejects_non_https(self):
        from igris_os.capabilities.host import open_chrome_window
        result = open_chrome_window({"url": "http://insecure.example"})
        self.assertFalse(result.ok)

    @patch("igris_os.capabilities.host._find_chrome",
           return_value=r"C:\chrome\chrome.exe")
    @patch("igris_os.capabilities.host.subprocess.Popen")
    def test_launches_new_window(self, popen, _find):
        from igris_os.capabilities.host import open_chrome_window
        result = open_chrome_window({"url": "https://github.com/org/a"})
        self.assertTrue(result.ok)
        args = popen.call_args[0][0]
        self.assertIn("--new-window", args)
        self.assertIn("https://github.com/org/a", args)


if __name__ == "__main__":
    unittest.main()


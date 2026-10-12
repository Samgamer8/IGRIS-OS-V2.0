import unittest
from unittest.mock import patch

from igris_os.evolution.github_sources import (
    RepositoryFile, _github_repo_parts, _make_evidence,
)


class GitHubSourceTests(unittest.TestCase):
    def test_repository_url_extracts_owner_name_and_optional_branch(self):
        self.assertEqual(
            _github_repo_parts("https://github.com/example/project/tree/main"),
            ("example", "project", "main"),
        )

    def test_rejects_non_github_and_repo_less_urls(self):
        for url in ("http://github.com/a/b", "https://github.com/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _github_repo_parts(url)

    def test_evidence_ids_and_line_ranges_are_stable(self):
        with patch("igris_os.evolution.github_sources.CHUNK_LINES", 2):
            chunks = _make_evidence(
                (RepositoryFile("README.md", "one\ntwo\nthree"),), "S2")
        self.assertEqual([chunk.evidence_id for chunk in chunks], ["S2-R001", "S2-R002"])
        self.assertEqual([(chunk.line_start, chunk.line_end) for chunk in chunks], [(1, 2), (3, 3)])


if __name__ == "__main__":
    unittest.main()

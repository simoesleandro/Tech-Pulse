"""Unit tests for semantic deduplication of titles (bigram similarity)."""
import pytest
from app.services.ingest import _title_bigrams, _titles_are_similar


class TestTitleBigrams:
    def test_basic_bigrams(self):
        bg = _title_bigrams("python async patterns")
        assert "python_async" in bg
        assert "async_patterns" in bg

    def test_punctuation_stripped(self):
        bg = _title_bigrams("Python: async patterns!")
        assert "python_async" in bg

    def test_case_insensitive(self):
        assert _title_bigrams("python async") == _title_bigrams("PYTHON ASYNC")

    def test_empty_title_returns_empty(self):
        assert _title_bigrams("") == frozenset()

    def test_single_word_returns_empty(self):
        assert _title_bigrams("python") == frozenset()

    def test_returns_frozenset(self):
        assert isinstance(_title_bigrams("hello world"), frozenset)


class TestTitlesSimilar:
    def test_identical_titles_are_similar(self):
        assert _titles_are_similar("Python async guide", "Python async guide")

    def test_clearly_different_titles(self):
        assert not _titles_are_similar(
            "Python async guide",
            "Kubernetes deployment best practices",
        )

    def test_empty_title_not_similar(self):
        assert not _titles_are_similar("", "Python async")
        assert not _titles_are_similar("Python async", "")

    def test_custom_threshold(self):
        # These titles share the bigram "python_async" (Jaccard ~0.2),
        # similar at threshold=0.1 but not at the default 0.65.
        assert _titles_are_similar(
            "Python async programming guide",
            "Python async framework tutorial",
            threshold=0.1,
        )
        assert not _titles_are_similar(
            "Python async programming guide",
            "Python async framework tutorial",
        )


class TestPrecomputedBigramsConsistency:
    """Verifies that precomputed bigrams produce the same result as _titles_are_similar."""

    def test_precomputed_same_result(self):
        from app.services.ingest import _title_bigrams, _titles_are_similar
        titles = ["Python async guide", "How to use FastAPI", "Kubernetes tutorial"]
        new_title = "Python Async Guide"

        # baseline
        via_function = any(_titles_are_similar(new_title, t) for t in titles)

        # precomputed
        precomputed = [_title_bigrams(t) for t in titles]
        new_bg = _title_bigrams(new_title)
        via_precomputed = any(
            (len(new_bg & bg) / len(new_bg | bg)) >= 0.65
            if new_bg and bg else False
            for bg in precomputed
        )

        assert via_function == via_precomputed

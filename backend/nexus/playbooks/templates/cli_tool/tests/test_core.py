from app.core import word_count


def test_counts():
    assert word_count("a b\nc") == {"words": 3, "lines": 2, "chars": 5}

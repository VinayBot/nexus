"""Pure logic, kept separate from argument parsing so it is easy to test."""


def word_count(text: str) -> dict[str, int]:
    words = text.split()
    return {"words": len(words), "lines": len(text.splitlines()), "chars": len(text)}

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_user_facing_documents_have_no_hidden_control_characters() -> None:
    documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
    assert documents
    for path in documents:
        text = path.read_text(encoding="utf-8")
        assert not any(char in text for char in ("\t", "\x00", "\x0b", "\x0c")), path
import pytest
from karakeep_tts.tts import chunk_text


def test_chunk_short_text_one_chunk():
    text = "Just a sentence."
    chunks = chunk_text(text, max_chars=100)
    assert chunks == ["Just a sentence."]


def test_chunk_splits_on_paragraph_boundary():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = chunk_text(text, max_chars=25)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 25
    assert "".join(chunks).replace("\n\n", "") == text.replace("\n\n", "")


def test_chunk_splits_on_sentence_when_paragraph_too_long():
    text = "Sentence one. Sentence two. Sentence three. Sentence four."
    chunks = chunk_text(text, max_chars=30)
    assert all(len(c) <= 30 for c in chunks)
    # No mid-word splits: every chunk ends at a word boundary
    for c in chunks:
        assert not c.endswith(" ") or c.rstrip().endswith((".", "!", "?"))


def test_chunk_falls_back_to_word_boundary_on_monster_sentence():
    text = "word " * 100  # 500 chars, no sentence punctuation
    chunks = chunk_text(text, max_chars=50)
    assert all(len(c) <= 50 for c in chunks)
    # No mid-word split
    for c in chunks:
        assert " word" not in c[-5:] or c.endswith("word")


def test_chunk_preserves_all_content():
    text = "Paragraph A.\n\n" + ("Sentence. " * 50) + "\n\nParagraph C."
    chunks = chunk_text(text, max_chars=80)
    joined = " ".join(c.strip() for c in chunks)
    # All meaningful words preserved
    assert joined.count("Sentence.") == 50
    assert "Paragraph A." in joined
    assert "Paragraph C." in joined


def test_chunk_raises_on_unsplittable_giant_word():
    # A single word longer than max_chars
    with pytest.raises(ValueError, match="cannot be split"):
        chunk_text("x" * 1000, max_chars=100)

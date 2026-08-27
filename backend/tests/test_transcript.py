"""Tests for transcript parsing and (de)serialization."""
import json

from app.models.job import Segment, Transcript, Translation, TranslatedSegment
from app.services import transcription, translation


def test_transcript_round_trip(tmp_path):
    t = Transcript(
        language="en",
        duration=42.5,
        segments=[
            Segment(id=1, start=0.0, end=2.5, text="Hello world."),
            Segment(id=2, start=2.5, end=5.0, text="How are you?"),
        ],
    )
    p = tmp_path / "transcript.json"
    transcription.save_transcript(t, p)
    loaded = transcription.load_transcript(p)
    assert loaded.language == "en"
    assert loaded.duration == 42.5
    assert len(loaded.segments) == 2
    assert loaded.segments[0].text == "Hello world."
    assert loaded.segments[1].start == 2.5


def test_translation_round_trip(tmp_path):
    tr = Translation(
        source_language="en",
        target_language="fa",
        segments=[
            TranslatedSegment(id=1, start=0.0, end=2.5, text="Hello.", translation="سلام."),
            TranslatedSegment(id=2, start=2.5, end=5.0, text="Bye.", translation="خداحافظ."),
        ],
    )
    p = tmp_path / "translation.json"
    translation.save_translation(tr, p)
    loaded = translation.load_translation(p)
    assert loaded.source_language == "en"
    assert loaded.target_language == "fa"
    assert loaded.segments[1].translation == "خداحافظ."


def test_transcript_missing_file_raises(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        transcription.load_transcript(tmp_path / "nope.json")


def test_segment_id_order_preserved():
    """Gemini must preserve segment IDs; we check the data structure carries them."""
    segs = [Segment(id=7, start=1, end=2, text="a"), Segment(id=3, start=2, end=3, text="b")]
    t = Transcript(language="en", duration=10, segments=segs)
    assert [s.id for s in t.segments] == [7, 3]

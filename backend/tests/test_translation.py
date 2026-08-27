"""Tests for Gemini response parsing (defensive JSON handling)."""
import pytest

from app.services.translation import _parse_response, _strip_fences, TranslationError


def test_parse_clean_json():
    raw = '[{"id":1,"translation":"سلام"},{"id":2,"translation":"خوبم"}]'
    out = _parse_response(raw, [1, 2])
    assert out == [{"id": 1, "translation": "سلام"}, {"id": 2, "translation": "خوبم"}]


def test_parse_json_with_fences():
    raw = '```json\n[{"id":1,"translation":"سلام"}]\n```'
    out = _parse_response(raw, [1])
    assert out == [{"id": 1, "translation": "سلام"}]


def test_parse_json_with_surrounding_text():
    raw = 'Here is the translation:\n[{"id":1,"translation":"سلام"}]\nDone.'
    out = _parse_response(raw, [1])
    assert out == [{"id": 1, "translation": "سلام"}]


def test_parse_json_with_extra_keys_ignored():
    raw = '[{"id":1,"translation":"سلام","note":"x"},{"id":2,"text":"خوبم"}]'
    out = _parse_response(raw, [1, 2])
    assert out[0]["translation"] == "سلام"
    assert out[1]["translation"] == "خوبم"  # falls back to 'text'


def test_parse_invalid_json_raises():
    with pytest.raises(TranslationError):
        _parse_response("not json at all", [1])


def test_parse_non_array_raises():
    with pytest.raises(TranslationError):
        _parse_response('{"id":1,"translation":"x"}', [1])


def test_parse_missing_ids_warning_but_returns_found():
    # Gemini returns fewer items than expected; we keep what we got.
    raw = '[{"id":1,"translation":"سلام"}]'
    out = _parse_response(raw, [1, 2])
    assert out == [{"id": 1, "translation": "سلام"}]


def test_strip_fences_plain():
    assert _strip_fences('[{"id":1}]') == '[{"id":1}]'


def test_strip_fences_json_fence():
    assert _strip_fences('```json\n[{"id":1}]\n```') == '[{"id":1}]'


def test_strip_fences_plain_fence():
    assert _strip_fences('```\n[{"id":1}]\n```') == '[{"id":1}]'

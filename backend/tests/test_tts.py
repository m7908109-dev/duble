"""Tests for the TTS adapter interface and provider registry."""
import pytest

from app.services.tts import registry
from app.services.tts.base import TTSProvider
from app.services.tts.edge import EdgeTTSProvider
from app.services.tts.piper import PiperTTSProvider


def test_registry_lists_providers():
    providers = registry.list_providers()
    assert "edge" in providers
    assert "piper" in providers


def test_get_provider_returns_correct_type():
    edge = registry.get("edge")
    assert isinstance(edge, EdgeTTSProvider)
    assert isinstance(edge, TTSProvider)
    piper = registry.get("piper")
    assert isinstance(piper, PiperTTSProvider)


def test_get_unknown_provider_raises():
    with pytest.raises(ValueError):
        registry.get("nonexistent-provider")


def test_edge_default_voice_falls_back():
    """For an unknown language, edge provider should still return a voice id."""
    edge = EdgeTTSProvider()
    voice = edge.default_voice("xx")
    assert isinstance(voice, str)
    assert len(voice) > 0


def test_piper_without_model_has_no_voices():
    piper = PiperTTSProvider()
    # No model configured -> empty list, NOT an exception.
    voices = piper.available_voices()
    assert voices == []


def test_piper_supports_lang_without_model():
    piper = PiperTTSProvider()
    # supports_lang should be False when no model is configured.
    assert piper.supports_lang("fa") is False


def test_all_voices_aggregates_across_providers():
    voices = registry.all_voices()
    # Edge has 300+ voices; piper has 0 by default. Should not crash.
    assert isinstance(voices, list)

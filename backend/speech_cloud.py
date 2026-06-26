"""Google Cloud Speech-to-Text + Text-to-Speech, using the same service-account
credential as Vertex AI. Used only when online; the browser handles STT/TTS offline.

Gated by USE_CLOUD_SPEECH=true in .env. If the libraries/credentials aren't
available, cloud_available() returns False and the frontend stays on browser speech.
"""
import os
import json

from dotenv import load_dotenv

load_dotenv()

import gcp_creds

USE_CLOUD_SPEECH = os.getenv("USE_CLOUD_SPEECH", "false").strip().lower() == "true"
# Credentials resolved from a file (local) or GCP_CREDENTIALS_JSON env var (cloud).
_CRED_PATH = gcp_creds.credentials_path()

_stt_client = None
_tts_client = None
_init_error = None

# BCP-47 language codes for Cloud Speech (mirrors the frontend selector).
LANG_MAP = {"en": "en-US", "hi": "hi-IN", "es": "es-ES",
            "en-US": "en-US", "hi-IN": "hi-IN", "es-ES": "es-ES"}

# Natural voices per language (Cloud TTS). Falls back to language default if absent.
VOICE_MAP = {
    "en-US": "en-US-Neural2-C",
    "hi-IN": "hi-IN-Neural2-A",
    "es-ES": "es-ES-Neural2-A",
}


def _ensure_clients():
    global _stt_client, _tts_client, _init_error
    if _init_error is not None:
        return False
    if _stt_client is not None and _tts_client is not None:
        return True
    if not USE_CLOUD_SPEECH:
        return False
    if not _CRED_PATH or not os.path.exists(_CRED_PATH):
        _init_error = "credentials missing"
        return False
    try:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _CRED_PATH
        from google.cloud import speech, texttospeech
        _stt_client = speech.SpeechClient()
        _tts_client = texttospeech.TextToSpeechClient()
        return True
    except Exception as e:
        _init_error = str(e)
        return False


def cloud_available():
    return _ensure_clients()


def transcribe(audio_bytes, language="en", phrases=None):
    """Audio bytes -> transcript. `phrases` boosts domain vocabulary (codes, etc.).
    Returns (text, confidence)."""
    if not _ensure_clients():
        raise RuntimeError("Cloud STT not available")
    from google.cloud import speech

    lang = LANG_MAP.get(language, "en-US")
    audio = speech.RecognitionAudio(content=audio_bytes)

    def _config(with_adaptation):
        # Domain-vocabulary biasing via SpeechContext (simpler + more robust than
        # SpeechAdaptation/PhraseSet, which can be rejected by the v1 API).
        contexts = None
        if with_adaptation and phrases:
            contexts = [speech.SpeechContext(phrases=[p for p in phrases[:500]], boost=15.0)]
        return speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            language_code=lang,
            enable_automatic_punctuation=True,
            model="latest_long",
            speech_contexts=contexts,
        )

    def _run(cfg):
        resp = _stt_client.recognize(config=cfg, audio=audio)
        text, conf = "", 0.0
        for result in resp.results:
            alt = result.alternatives[0]
            text += alt.transcript + " "
            conf = max(conf, alt.confidence or 0.0)
        return text.strip(), conf

    # Try with vocabulary biasing; if that errors (e.g. context rejected), retry
    # plain so a config quirk never breaks transcription entirely.
    try:
        return _run(_config(True))
    except Exception:
        return _run(_config(False))


def synthesize(text, language="en"):
    """Text -> MP3 audio bytes in a natural voice."""
    if not _ensure_clients():
        raise RuntimeError("Cloud TTS not available")
    from google.cloud import texttospeech

    lang = LANG_MAP.get(language, "en-US")
    voice_name = VOICE_MAP.get(lang)
    voice = texttospeech.VoiceSelectionParams(
        language_code=lang,
        name=voice_name,
    ) if voice_name else texttospeech.VoiceSelectionParams(language_code=lang)
    synth_input = texttospeech.SynthesisInput(text=text)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=1.0,
    )
    resp = _tts_client.synthesize_speech(
        input=synth_input, voice=voice, audio_config=audio_config
    )
    return resp.audio_content

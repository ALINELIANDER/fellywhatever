"""Offline TTS wrapper around AI4Bharat Indic Parler-TTS.

Used ONLY during lesson preparation. The model is loaded on demand and can be
explicitly unloaded (unload()) so nothing TTS-related stays in RAM during the
live classroom session.

Indic Parler-TTS uses TWO tokenizers:
  * prompt tokenizer  -> bundled with the model
  * description tokenizer -> google/flan-t5-large (cached locally by setup)
The description (voice caption) is always English; the transcript carries the
actual Hindi/Santali text.
"""

import gc
from pathlib import Path

import numpy as np
import soundfile as sf

from config import (
    FLAN_T5_TOKENIZER_DIR,
    FLAN_T5_TOKENIZER_REPO,
    SAMPLE_RATE,
    TTS_MODEL_DIR,
    TTS_MODEL_REPO,
)

# Voice captions (description). English only, as the flan-t5 tokenizer is
# English-centric and the model expects English description captions.
DESCRIPTION = {
    "hindi": (
        "Divya's voice is clear and slow with very high quality audio, "
        "slightly expressive, spoken in Hindi with no background noise."
    ),
    "santali": (
        "A female speaker speaks clearly and slowly in Santali with very high "
        "quality audio, no background noise."
    ),
}

_MAX_NEW_TOKENS = {"hindi": 80, "santali": 80}


class TTSError(Exception):
    pass


class TTSManager:
    """Load / generate / unload lifecycle for Indic Parler-TTS (CPU)."""

    def __init__(self, model_dir=TTS_MODEL_DIR):
        self.model_dir = Path(model_dir)
        self.model = None
        self.tokenizer = None
        self.description_tokenizer = None
        self.loaded = False

    # ---------------------------------------------------------------- model dir
    def ensure_model_dir(self):
        """Make sure the full model lives in the local offline directory.

        Runs once during setup; afterwards everything is offline. If the model
        weights are missing or a previous download was interrupted (left an
        *.incomplete blob behind), re-download / resume via snapshot_download.
        """
        incomplete = list(self.model_dir.glob("*.incomplete"))
        has_weights = (self.model_dir / "model.safetensors").exists()

        if self.model_dir.exists() and any(self.model_dir.iterdir()) and has_weights and not incomplete:
            return str(self.model_dir)

        for lock in self.model_dir.glob("*.lock"):
            try:
                lock.unlink()
            except OSError:
                pass

        if not TTS_MODEL_REPO:
            raise TTSError("TTS model not present locally and no remote repo configured.")

        from huggingface_hub import snapshot_download

        self.model_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_download(
            repo_id=TTS_MODEL_REPO,
            local_dir=str(self.model_dir),
            local_dir_use_symlinks=False,
        )
        if not (self.model_dir / "model.safetensors").exists():
            raise TTSError("Model download finished but model.safetensors is missing.")
        return path

    def _ensure_description_tokenizer(self):
        """Local copy of the flan-t5-large tokenizer (needs internet once)."""
        if FLAN_T5_TOKENIZER_DIR.exists() and any(FLAN_T5_TOKENIZER_DIR.iterdir()):
            return str(FLAN_T5_TOKENIZER_DIR)
        from huggingface_hub import snapshot_download

        FLAN_T5_TOKENIZER_DIR.mkdir(parents=True, exist_ok=True)
        return snapshot_download(
            repo_id=FLAN_T5_TOKENIZER_REPO,
            local_dir=str(FLAN_T5_TOKENIZER_DIR),
            local_dir_use_symlinks=False,
            allow_patterns=[
                "tokenizer_config.json",
                "tokenizer.json",
                "spiece.model",
                "special_tokens_map.json",
                "config.json",
            ],
        )

    # --------------------------------------------------------------------- load
    def load(self):
        if self.loaded:
            return self
        model_dir = self.ensure_model_dir()
        try:
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer

            self.model = _load_model(model_dir)
            self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
            self.description_tokenizer = AutoTokenizer.from_pretrained(
                self._ensure_description_tokenizer()
            )
            self.model.eval()
            self.loaded = True
        except Exception as exc:
            raise TTSError(f"Failed to load Indic Parler-TTS: {exc}") from exc
        return self

    # ---------------------------------------------------------------- synthesis
    def synthesize(self, text, output_path, lang):
        """Synthesize speech for `text` and save as 22.05 kHz WAV."""
        if not self.loaded:
            self.load()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        description = DESCRIPTION.get(lang, DESCRIPTION["hindi"])
        description_inputs = self.description_tokenizer(description, return_tensors="pt")
        prompt = (text or "").strip()
        prompt_inputs = self.tokenizer(prompt, return_tensors="pt")

        max_tokens = _MAX_NEW_TOKENS.get(lang, 80)
        gen_kwargs = dict(
            max_new_tokens=max_tokens,
            do_sample=True,
            temperature=1.0,
            top_p=0.95,
        )
        try:
            generation = self.model.generate(
                input_ids=description_inputs.input_ids,
                attention_mask=description_inputs.attention_mask,
                prompt_input_ids=prompt_inputs.input_ids,
                prompt_attention_mask=prompt_inputs.attention_mask,
                **gen_kwargs,
            )
        except TypeError:
            generation = self.model.generate(
                description_inputs.input_ids,
                prompt_inputs.input_ids,
                **gen_kwargs,
            )

        audio = generation.cpu().numpy().squeeze()
        audio = np.asarray(audio, dtype=np.float32)
        sf.write(str(output_path), audio, SAMPLE_RATE)
        return str(output_path)

    # ------------------------------------------------------------------- unload
    def unload(self):
        self.model = None
        self.tokenizer = None
        self.description_tokenizer = None
        self.loaded = False
        gc.collect()


def _load_model(model_dir):
    import torch

    from parler_tts import ParlerTTSForConditionalGeneration

    # Prefer explicit dtype for determinism; fall back to the default loader if
    # the running transformers version rejects the `dtype` keyword.
    try:
        return ParlerTTSForConditionalGeneration.from_pretrained(
            model_dir, dtype=torch.float32
        )
    except TypeError:
        return ParlerTTSForConditionalGeneration.from_pretrained(model_dir)
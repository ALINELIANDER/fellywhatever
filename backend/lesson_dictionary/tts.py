"""Offline TTS wrapper around AI4Bharat Indic Parler-TTS.

Lesson-preparation path (default): loads on demand, writes WAV at 22 050 Hz,
unloads after use (nothing stays in RAM during the live classroom session).

Live-classroom path: pass ``device="cuda"`` and ``dtype=torch.float16`` to the
constructor; call ``sample_rate`` (44 100 Hz, explicit) for live audio; use
``synthesize_array()`` which returns a mono float32 numpy array in memory.

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

_MAX_NEW_TOKENS = {"hindi": 256, "santali": 256}


class TTSError(Exception):
    pass


class TTSManager:
    """Load / generate / unload lifecycle for Indic Parler-TTS.

    Parameters
    ----------
    device / dtype:
        ``"cuda"`` + ``torch.float16`` (live path) loads the model in half
        precision on GPU (~1.8 GB VRAM).  The default is ``"cpu"`` /
        ``torch.float32`` which preserves the existing lesson-prep behaviour.
    sample_rate:
        Overrides the output sample rate.  The lesson path uses the module
        default 22 050 Hz; the live path passes 44 100 Hz to match
        ``pipeline/config.TTS_SAMPLE_RATE`` (and ``live_classroom.config``).
    """

    def __init__(
        self,
        model_dir=TTS_MODEL_DIR,
        device: str = "cpu",
        dtype=None,
        sample_rate: int | None = None,
    ):
        self.model_dir = Path(model_dir)
        self.device = device
        self.dtype = dtype
        self.sample_rate = sample_rate if sample_rate is not None else SAMPLE_RATE
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
    def load(self, device=None, dtype=None):
        if self.loaded:
            return self
        if device is not None:
            self.device = device
        if dtype is not None:
            self.dtype = dtype
        model_dir = self.ensure_model_dir()
        try:
            from parler_tts import ParlerTTSForConditionalGeneration
            from transformers import AutoTokenizer

            self.model = _load_model(model_dir, device=self.device, dtype=self.dtype)
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
        """Synthesize speech for ``text`` and save as a WAV at ``self.sample_rate``."""
        audio = self.synthesize_array(text, lang)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), audio, self.sample_rate)
        return str(output_path)

    def synthesize_array(self, text, lang):
        """Synthesize speech for ``text`` and return a mono float32 numpy array.

        The sample rate is ``self.sample_rate`` (22 050 Hz lesson prep,
        44 100 Hz live path). Tensors are placed on ``self.device`` when the
        model was loaded on the GPU.
        """
        if not self.loaded:
            self.load()

        import torch

        dev = self.device or "cpu"

        def _to(x):
            return x.to(dev)

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
        with torch.inference_mode():
            try:
                generation = self.model.generate(
                    input_ids=_to(description_inputs.input_ids),
                    attention_mask=_to(description_inputs.attention_mask),
                    prompt_input_ids=_to(prompt_inputs.input_ids),
                    prompt_attention_mask=_to(prompt_inputs.attention_mask),
                    **gen_kwargs,
                )
            except TypeError:
                generation = self.model.generate(
                    _to(description_inputs.input_ids),
                    _to(prompt_inputs.input_ids),
                    **gen_kwargs,
                )

        audio = generation.detach().float().cpu().numpy().squeeze()
        audio = np.asarray(audio, dtype=np.float32)
        return audio

    # ------------------------------------------------------------------- unload
    def unload(self):
        self.model = None
        self.tokenizer = None
        self.description_tokenizer = None
        self.loaded = False
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def _load_model(model_dir, device="cpu", dtype=None):
    import torch

    from parler_tts import ParlerTTSForConditionalGeneration

    if dtype is None:
        dtype = torch.float16 if device == "cuda" else torch.float32
    # Prefer explicit dtype for determinism; fall back to the default loader if
    # the running transformers version rejects the `dtype` keyword.
    try:
        model = ParlerTTSForConditionalGeneration.from_pretrained(
            model_dir, dtype=dtype
        )
    except TypeError:
        model = ParlerTTSForConditionalGeneration.from_pretrained(
            model_dir, torch_dtype=dtype
        )
    model = model.to(device)
    return model
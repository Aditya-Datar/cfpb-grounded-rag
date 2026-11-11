"""Load a trained complaint classifier and predict on new narratives.

    from cfpb.classify.predict import ComplaintClassifier
    clf = ComplaintClassifier("outputs/classifier/product/best")
    clf.predict(["I was charged twice on my credit card ..."])
    # -> DataFrame: label, prob, top_k [(label, prob), ...]

Used by later stages (routing retrieval by product) and the Streamlit demo.
Works on CPU (about 1-3 narratives/sec for long texts) or GPU.
"""
import json
from pathlib import Path

import pandas as pd
import torch
import transformers
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from cfpb.classify.data import encode
from cfpb.classify.train import pick_device_and_dtype, predict
from cfpb.data.clean import clean_narrative


class ComplaintClassifier:
    def __init__(self, model_dir, max_len: int | None = None, head_tokens: int | None = None):
        model_dir = Path(model_dir)
        transformers.logging.set_verbosity_error()
        # Reuse the truncation settings the model was trained with, if recorded.
        info_path = model_dir.parent / "run_info.json"
        args = json.loads(info_path.read_text())["args"] if info_path.exists() else {}
        self.max_len = max_len or args.get("max_len", 512)
        self.head_tokens = head_tokens or args.get("head_tokens", 128)
        self.device, self.dtype = pick_device_and_dtype()
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(self.device)
        self.model.eval()
        self.labels = [self.model.config.id2label[i] for i in range(self.model.config.num_labels)]

    def predict_proba(self, texts, clean: bool = True, batch_size: int = 32):
        """Probabilities, shape (n, num_labels), in self.labels order. Raw CFPB
        text is cleaned first (clean_narrative is safe on already-clean text)."""
        texts = [clean_narrative(t) if clean else t for t in texts]
        enc = encode(texts, self.tokenizer, self.max_len, self.head_tokens)
        with torch.no_grad():
            return predict(self.model, enc, batch_size, self.device, self.dtype,
                           self.tokenizer.pad_token_id)

    def predict(self, texts, clean: bool = True, top_k: int = 3, batch_size: int = 32) -> pd.DataFrame:
        probs = self.predict_proba(texts, clean, batch_size)
        order = probs.argsort(1)[:, ::-1][:, :top_k]
        return pd.DataFrame({
            "label": [self.labels[o[0]] for o in order],
            "prob": [float(probs[i, o[0]]) for i, o in enumerate(order)],
            "top_k": [[(self.labels[j], round(float(probs[i, j]), 4)) for j in o]
                      for i, o in enumerate(order)],
        })

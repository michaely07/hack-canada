from sentence_transformers import SentenceTransformer
import numpy as np


class BatchEmbedder:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("Model loaded.")

    def encode_batch(self, texts: list[str], batch_size=64) -> list[np.ndarray]:
        """Encode a list of texts, returns list of numpy arrays."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False)
        return list(embeddings)

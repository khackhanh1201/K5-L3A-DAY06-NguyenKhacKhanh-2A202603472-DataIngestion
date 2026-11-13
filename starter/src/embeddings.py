"""Real local embedding model via Sentence Transformers (no API key, cost 0).

Default: ``intfloat/multilingual-e5-small`` (384 dims). E5 models require the
prefixes ``query: `` and ``passage: `` (see the model card); vectors are
L2-normalized so cosine similarity is well defined. Errors are raised, never
replaced by mock vectors.
"""
from typing import Protocol

DEFAULT_MODEL = "intfloat/multilingual-e5-small"


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, question: str) -> list[float]: ...


class MyEmbedder:
    def __init__(self, model_name: str = DEFAULT_MODEL, batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer  # heavy import, keep lazy

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name)
        self.dimensions = int(self.model.get_sentence_embedding_dimension())
        self._e5 = "e5" in model_name.lower()

    def _encode(self, texts: list[str], progress: bool) -> list[list[float]]:
        vectors = self.model.encode(texts, batch_size=self.batch_size, normalize_embeddings=True,
                                    show_progress_bar=progress, convert_to_numpy=True)
        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self._e5:
            texts = [f"passage: {t}" for t in texts]
        return self._encode(texts, progress=len(texts) > 64)

    def embed_queries(self, questions: list[str]) -> list[list[float]]:
        if self._e5:
            questions = [f"query: {q}" for q in questions]
        return self._encode(questions, progress=False)

    def embed_query(self, question: str) -> list[float]:
        return self.embed_queries([question])[0]

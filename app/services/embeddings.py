import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Union

class SentenceTransformerEmbedding():
    """
    A class for generating sentence embeddings using the sentence-transformers library.
    """
    def __init__(self, model_name: str):
        """
        Initializes the embedding model.

        Args:
            model_name (str): The name of the pre-trained sentence-transformer model to use
                              (e.g., 'all-MiniLM-L6-v2', 'paraphrase-MiniLM-L6-v2').
                              See https://www.sbert.net/docs/pretrained_models.html
        """
        # Load the specified Sentence Transformer model
        # This might download the model if it's not cached locally.
        self.model = SentenceTransformer(model_name, device='cuda')

    def create_embeddings(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Generates embeddings for the given text(s).

        Args:
            texts (Union[str, List[str]]): A single string or a list of strings to embed.

        Returns:
            np.ndarray: A numpy array containing the embedding(s).
                        If input is a single string, returns a 1D array.
                        If input is a list of strings, returns a 2D array where each row
                        is an embedding for the corresponding input string.
        """
        embeddings = self.model.encode(texts, batch_size=32, normalize_embeddings=True)
        return embeddings

    def get_embedding_dimension(self) -> int:
        """
        Returns the dimension of the embeddings generated by the loaded model.

        Returns:
            int: The dimensionality of the embedding vectors.
        """
        # Retrieve the embedding dimension from the model
        return self.model.get_sentence_embedding_dimension()
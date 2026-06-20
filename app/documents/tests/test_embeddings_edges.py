from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from documents.services.embeddings import (
    FALLBACK_DIMENSIONS,
    _hash_embedding,
    cosine_similarity,
    get_embedding,
    get_embeddings_batch,
)


class EmbeddingTests(SimpleTestCase):
    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    @override_settings(OPENAI_API_KEY="")
    def test_hash_fallback_is_deterministic_normalized_and_handles_empty_text(self):
        first = get_embedding("quy trinh van hanh")
        second = get_embedding("quy trinh van hanh")
        self.assertEqual(first, second)
        self.assertEqual(len(first), FALLBACK_DIMENSIONS)
        self.assertAlmostEqual(sum(value * value for value in first), 1.0)
        self.assertEqual(_hash_embedding(""), [0.0] * FALLBACK_DIMENSIONS)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "key"})
    @patch("openai.OpenAI")
    def test_openai_embedding_success_and_failure_fallback(self, openai):
        client = openai.return_value
        client.embeddings.create.return_value = SimpleNamespace(
            data=[SimpleNamespace(embedding=[0.1, 0.2])]
        )
        self.assertEqual(get_embedding("text"), [0.1, 0.2])
        client.embeddings.create.assert_called_once()

        client.embeddings.create.side_effect = RuntimeError("offline")
        result = get_embedding("text")
        self.assertEqual(len(result), FALLBACK_DIMENSIONS)

    def test_cosine_similarity_handles_equal_orthogonal_zero_and_mismatch(self):
        self.assertEqual(cosine_similarity([1, 0], [1, 0]), 1.0)
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0.0)
        self.assertEqual(cosine_similarity([], [1]), 0.0)
        self.assertEqual(cosine_similarity(None, [1]), 0.0)
        self.assertEqual(cosine_similarity([1], [1, 2]), 0.0)
        self.assertEqual(cosine_similarity([0, 0], [1, 1]), 0.0)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "key"})
    @patch("openai.OpenAI")
    def test_batch_embeddings_split_requests_and_fallback_on_error(self, openai):
        client = openai.return_value

        def create(*, model, input):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[float(len(text))]) for text in input])

        client.embeddings.create.side_effect = create
        result = get_embeddings_batch(["x"] * 257)
        self.assertEqual(len(result), 257)
        self.assertEqual(client.embeddings.create.call_count, 2)

        client.embeddings.create.side_effect = RuntimeError("offline")
        fallback = get_embeddings_batch(["a", "b"])
        self.assertEqual(len(fallback), 2)
        self.assertTrue(all(len(item) == FALLBACK_DIMENSIONS for item in fallback))

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    @override_settings(OPENAI_API_KEY="")
    def test_batch_without_api_key_uses_local_embeddings(self):
        result = get_embeddings_batch(["a", "", None])
        self.assertEqual(len(result), 3)
        self.assertTrue(all(len(item) == FALLBACK_DIMENSIONS for item in result))

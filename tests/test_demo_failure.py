import pytest
pytest.importorskip("pydantic")
from lesson_generator.evaluation.evaluator import _local_failures

def test_demo_false_claim_is_detected_as_accuracy_failure():
    failures = _local_failures("RAG always fine-tunes the language model using retrieved documents.")
    assert "accuracy_and_grounding" in failures

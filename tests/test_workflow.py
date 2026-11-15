import json
from pathlib import Path
from types import SimpleNamespace
import pytest

pytest.importorskip("pydantic")
pytest.importorskip("langgraph")
from lesson_generator.graph.workflow import run_workflow
from lesson_generator.schemas import CriterionResult, EvaluationReport, RubricDimension

def report(passed):
    status = "PASS" if passed else "FAIL"
    vals = {d.value: CriterionResult(status=status, explanation="ok" if passed else "needs work",
             evidence="lesson text", failure_reasons=[] if passed else ["missing detail"],
             correction_instruction=None if passed else "Explain the missing point") for d in RubricDimension}
    return EvaluationReport(overall_status=status, **vals, summary_of_required_improvements="" if passed else "Improve clarity")

class MockGenerator:
    def __init__(self, lessons=None): self.lessons, self.feedback = list(lessons or []), []
    def generate(self, topic, feedback=None):
        self.feedback.append(list(feedback or []))
        return SimpleNamespace(markdown=self.lessons.pop(0) if self.lessons else "lesson")

class MockEvaluator:
    def __init__(self, results): self.results = list(results); self.seen = []
    def evaluate(self, lesson): self.seen.append(lesson); return self.results.pop(0)
    @staticmethod
    def _safe_failure(message): return report(False)

@pytest.mark.parametrize("sequence, expected_attempts", [([True], 1), ([False, True], 2), ([False, False, True], 3), ([False, False, False], 3)])
def test_attempt_sequences_and_rejection_history(tmp_path, sequence, expected_attempts):
    gen = MockGenerator([f"lesson-{i}" for i in range(3)])
    ev = MockEvaluator([report(x) for x in sequence])
    result = run_workflow("RAG", gen, ev, tmp_path)
    assert result["attempt"] == expected_attempts <= 3
    assert result["status"] == ("approved" if sequence[-1] else "rejected")
    history = json.loads((tmp_path / "rejection_log.json").read_text()) if len(sequence) > 1 or not sequence[-1] else []
    assert len(history) == len([x for x in sequence if not x])
    if result["status"] == "approved":
        assert (tmp_path / "final_lesson.md").exists()
    else:
        assert not (tmp_path / "final_lesson.md").exists()
        assert len(history) == 3

def test_feedback_reaches_generator_and_rejection_entries_complete(tmp_path):
    gen = MockGenerator(["bad", "good"]); ev = MockEvaluator([report(False), report(True)])
    run_workflow("RAG", gen, ev, tmp_path)
    assert gen.feedback[0] == []
    assert "accuracy_and_grounding" in gen.feedback[1][0]
    log = json.loads((tmp_path / "rejection_log.json").read_text())
    assert log[0]["attempt"] == 1
    assert log[0]["failed_criteria"][0]["evidence"] == "lesson text"
    assert log[0]["feedback_sent"]
    assert log[0]["summary_of_changes_in_next_attempt"]

def test_attempt_limit_is_validated(tmp_path):
    with pytest.raises(ValueError): run_workflow("RAG", MockGenerator(), MockEvaluator([]), tmp_path, 4)

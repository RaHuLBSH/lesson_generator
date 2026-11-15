"""Structured contracts for lesson generation and quality evaluation."""
from enum import Enum
from typing import TypedDict
from pydantic import BaseModel, Field, model_validator

class RubricDimension(str, Enum):
    ACCURACY_AND_GROUNDING = "accuracy_and_grounding"
    BEGINNER_FRIENDLY_LANGUAGE = "beginner_friendly_language"
    PRACTICAL_EXAMPLES = "practical_examples"
    CLEAR_EXPLANATIONS = "clear_explanations_without_unexplained_jargon"
    ESSENTIAL_CONCEPTS = "coverage_of_essential_concepts"
    LOGICAL_FLOW = "logical_teaching_flow"

class LessonDocument(BaseModel):
    topic: str
    markdown: str = Field(min_length=100)

class CriterionResult(BaseModel):
    status: str = Field(pattern="^(PASS|FAIL)$")
    explanation: str
    evidence: str
    failure_reasons: list[str] = Field(default_factory=list)
    correction_instruction: str | None = None

class EvaluationReport(BaseModel):
    overall_status: str = Field(pattern="^(PASS|FAIL)$")
    accuracy_and_grounding: CriterionResult
    beginner_friendly_language: CriterionResult
    practical_examples: CriterionResult
    clear_explanations_without_unexplained_jargon: CriterionResult
    coverage_of_essential_concepts: CriterionResult
    logical_teaching_flow: CriterionResult
    summary_of_required_improvements: str

    @model_validator(mode="after")
    def status_matches_criteria(self):
        fields = [getattr(self, d.value) for d in RubricDimension]
        expected = "PASS" if all(c.status == "PASS" for c in fields) else "FAIL"
        if self.overall_status != expected:
            raise ValueError("overall_status must pass only when every criterion passes")
        return self

class LessonState(TypedDict, total=False):
    topic: str
    lesson: str
    evaluation: EvaluationReport
    attempt: int
    max_attempts: int
    feedback: list[str]
    status: str

"""Independent evaluator combining deterministic gates and an LLM judge."""
import json
import re
from ..llm import create_client, model_name
from ..schemas import CriterionResult, EvaluationReport, RubricDimension

JUDGE_PROMPT = """You are an independent strict lesson reviewer. Judge each of exactly six dimensions: accuracy_and_grounding, beginner_friendly_language, practical_examples, clear_explanations_without_unexplained_jargon, coverage_of_essential_concepts, logical_teaching_flow. Check factual claims only against the supplied reference. If evidence is weak or uncertain, FAIL. Do not reward confidence or style in place of evidence. Return JSON matching the requested schema: overall_status, each dimension as {status: PASS|FAIL, explanation, evidence (short exact quote), failure_reasons (array), correction_instruction (string or null)}, and summary_of_required_improvements. Overall PASS only if all six pass. Do not use external assumptions."""

def _local_failures(lesson: str) -> dict[str, str]:
    text = lesson.strip()
    failures = {}
    if re.search(r"RAG always fine-tunes? the language model using retrieved documents", text, re.I):
        failures["accuracy_and_grounding"] = "The lesson incorrectly says RAG always fine-tunes the model; the reference describes retrieval followed by generation using retrieved context."
    if len(text) < 500 or len(re.findall(r"^#{1,3} .+", text, re.M)) < 5:
        failures["coverage_of_essential_concepts"] = "Lesson is too short or lacks sufficient section structure."
    step_match = re.search(r"step[- ]by[- ]step|step\s*1\b|first,", text, re.I)
    has_example_detail = bool(step_match and len(text[step_match.end():].strip()) >= 40)
    if not has_example_detail or not re.search(r"example|for instance", text, re.I):
        failures["practical_examples"] = "No clear practical step-by-step example was found."
    if not re.search(r"\b(what|introduction|meaning)\b", text, re.I):
        failures["logical_teaching_flow"] = "No introductory explanation was detected."
    if not text or "```" in text and text.count("```") % 2:
        failures["logical_teaching_flow"] = "Output is empty or has malformed Markdown code fences."
    return failures

class LessonEvaluator:
    def __init__(self, client=None, model: str | None = None, reference: str = ""):
        self.client = client or create_client()
        self.model = model or model_name()
        if not reference:
            from pathlib import Path
            reference = (Path(__file__).resolve().parents[3] / "references" / "rag_primer.md").read_text(encoding="utf-8")
        self.reference = reference

    def evaluate(self, lesson: str) -> EvaluationReport:
        if not isinstance(lesson, str) or not lesson.strip():
            return self._safe_failure("Lesson is empty or malformed.")
        try:
            response = self.client.chat.completions.create(model=self.model, temperature=0, messages=[
                {"role": "system", "content": JUDGE_PROMPT},
                {"role": "user", "content": f"REFERENCE:\n{self.reference}\n\nLESSON:\n{lesson}\n\nReturn only JSON."},
            ])
            raw = response.choices[0].message.content or ""
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
            data = json.loads(raw)
            report = EvaluationReport.model_validate(data)
        except Exception as exc:
            return self._safe_failure(f"Evaluator response or API call was invalid: {type(exc).__name__}.")
        local = _local_failures(lesson)
        for name, reason in local.items():
            item = getattr(report, name)
            item.status = "FAIL"
            item.explanation = reason
            item.evidence = "Deterministic lesson structure check."
            item.failure_reasons.append(reason)
            item.correction_instruction = "Add the missing section or a concrete step-by-step example, then re-evaluate."
        failed = [getattr(report, d.value) for d in RubricDimension if getattr(report, d.value).status == "FAIL"]
        report.overall_status = "FAIL" if failed else "PASS"
        if failed and not report.summary_of_required_improvements:
            report.summary_of_required_improvements = "; ".join(x.explanation for x in failed)
        return report

    @staticmethod
    def _safe_failure(reason: str) -> EvaluationReport:
        bad = lambda: CriterionResult(status="FAIL", explanation=reason, evidence="No trustworthy evaluator evidence.", failure_reasons=[reason], correction_instruction="Retry evaluation with a valid response; do not approve this lesson.")
        return EvaluationReport(overall_status="FAIL", **{d.value: bad() for d in RubricDimension}, summary_of_required_improvements=reason)

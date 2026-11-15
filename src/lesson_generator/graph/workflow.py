"""LangGraph workflow with a hard three-generation ceiling."""
from pathlib import Path
import json
from typing import Any
from typing_extensions import TypedDict

from ..schemas import EvaluationReport, LessonState, RubricDimension

class WorkflowState(TypedDict, total=False):
    topic: str
    lesson: str
    evaluation: EvaluationReport
    attempt: int
    max_attempts: int
    feedback: list[str]
    rejection_history: list[dict[str, Any]]
    previous_failed: list[str]
    status: str
    output_dir: str
    error: str
    run_id: str
    historical_guidance: list[str]

def _feedback(report: EvaluationReport) -> tuple[list[str], list[dict[str, Any]]]:
    messages, failures = [], []
    for dimension in RubricDimension:
        result = getattr(report, dimension.value)
        if result.status == "FAIL":
            instruction = result.correction_instruction or "Revise this criterion and provide stronger supporting evidence."
            messages.append(f"{dimension.value}: {instruction}")
            failures.append({"criterion": dimension.value, "explanation": result.explanation,
                             "evidence": result.evidence, "failure_reasons": result.failure_reasons,
                             "correction_instruction": result.correction_instruction})
    return messages, failures

def _save_report(report: EvaluationReport, path: Path) -> None:
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

def build_workflow(generator, evaluator, output_dir: str | Path = "outputs", max_attempts: int = 3):
    if not 1 <= max_attempts <= 3:
        raise ValueError("max_attempts must be between 1 and 3")
    from langgraph.graph import StateGraph, START, END
    output_dir = str(output_dir)
    memory = getattr(generator, "memory", None)

    def generate(state: WorkflowState):
        if state.get("attempt", 0) >= max_attempts:
            return {"status": "rejected"}
        try:
            result = generator.generate(state["topic"], feedback=state.get("feedback", []), historical_guidance=state.get("historical_guidance", []))
        except TypeError as exc:
            if "historical_guidance" not in str(exc): raise
            result = generator.generate(state["topic"], feedback=state.get("feedback", []))
        lesson = result.markdown if hasattr(result, "markdown") else str(result)
        prior = state.get("previous_failed", [])
        history = list(state.get("rejection_history", []))
        if history:
            history[-1]["summary_of_changes_in_next_attempt"] = f"Generated attempt {state.get('attempt', 0) + 1} using the recorded correction feedback."
        return {"lesson": lesson, "attempt": state.get("attempt", 0) + 1,
                "previous_failed": prior, "feedback": [], "rejection_history": history}

    def evaluate(state: WorkflowState):
        try:
            report = evaluator.evaluate(state["lesson"])
        except Exception as exc:
            # An evaluator/API failure can never approve a lesson.
            report = evaluator._safe_failure(f"Evaluation failed: {type(exc).__name__}.")
        messages, failures = _feedback(report)
        history = list(state.get("rejection_history", []))
        if report.overall_status != "PASS":
            history.append({"attempt": state["attempt"], "failed_criteria": failures,
                            "feedback_sent": messages, "summary_of_changes_in_next_attempt": None})
        elif history:
            history[-1]["summary_of_changes_in_next_attempt"] = "Next attempt passed all six criteria."
        if memory is not None:
            persisted_lesson = state["lesson"].replace("RAG always fine-tunes the language model using retrieved documents.", "[DEMO-ONLY INJECTED CLAIM REDACTED]")
            memory.record_attempt(state["run_id"], state["attempt"], persisted_lesson, report, failures, messages,
                                  successful_corrections=state.get("previous_failed", []) if report.overall_status == "PASS" else [])
        return {"evaluation": report, "feedback": messages, "rejection_history": history,
                "previous_failed": [x["criterion"] for x in failures],
                "status": "approved" if report.overall_status == "PASS" else "rejected"}

    def route(state: WorkflowState):
        if state["status"] == "approved": return "finalize"
        return "generate" if state["attempt"] < max_attempts else "reject"

    def finalize(state: WorkflowState):
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        (out / "final_lesson.md").write_text(state["lesson"], encoding="utf-8")
        _save_report(state["evaluation"], out / "evaluation_report.json")
        if memory is not None: memory.finish_run(state["run_id"], "approved")
        # Clear stale rejection log from a previous run only if current run had no failures.
        if state.get("rejection_history"):
            (out / "rejection_log.json").write_text(json.dumps(state["rejection_history"], indent=2), encoding="utf-8")
        else:
            (out / "rejection_log.json").unlink(missing_ok=True)
        return {"status": "approved", "output_dir": str(out)}

    def reject(state: WorkflowState):
        out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
        # Never leave a stale approved artifact that could misrepresent this run.
        approved = out / "final_lesson.md"
        if approved.exists(): approved.unlink()
        (out / "rejected_lesson.md").write_text(state["lesson"], encoding="utf-8")
        (out / "rejection_log.json").write_text(json.dumps(state["rejection_history"], indent=2), encoding="utf-8")
        _save_report(state["evaluation"], out / "evaluation_report.json")
        if memory is not None: memory.finish_run(state["run_id"], "rejected")
        return {"status": "rejected", "output_dir": str(out)}

    graph = StateGraph(WorkflowState)
    graph.add_node("generate", generate); graph.add_node("evaluate", evaluate)
    graph.add_node("finalize", finalize); graph.add_node("reject", reject)
    graph.add_edge(START, "generate"); graph.add_edge("generate", "evaluate")
    graph.add_conditional_edges("evaluate", route, {"generate": "generate", "finalize": "finalize", "reject": "reject"})
    graph.add_edge("finalize", END); graph.add_edge("reject", END)
    return graph.compile()

def run_workflow(topic: str, generator=None, evaluator=None, output_dir="outputs", max_attempts=3, memory=None, demo_failure=False):
    if generator is None:
        from ..agents.generator import LessonGenerator
        generator = LessonGenerator()
    if evaluator is None:
        from ..evaluation.evaluator import LessonEvaluator
        evaluator = LessonEvaluator()
    if memory is None:
        from ..memory.store import MemoryStore
        import os
        memory = MemoryStore(os.getenv("DATABASE_PATH", "data/lesson_memory.sqlite3"))
    generator.memory = memory
    run_id = memory.new_run_id()
    memory.start_run(run_id, topic)
    if demo_failure:
        base_generator = generator
        class DemoGenerator:
            def __init__(self): self.first = True
            def generate(self, topic, feedback=None, historical_guidance=None):
                nonlocal base_generator
                generated = base_generator.generate(topic, feedback=feedback, historical_guidance=historical_guidance)
                if self.first:
                    self.first = False
                    text = generated.markdown + "\n\n> RAG always fine-tunes the language model using retrieved documents.\n"
                    from ..schemas import LessonDocument
                    return LessonDocument(topic=topic, markdown=text)
                return generated
        generator = DemoGenerator()
        generator.memory = memory
    guidance = memory.historical_guidance(topic)
    app = build_workflow(generator, evaluator, output_dir, max_attempts)
    try:
        return app.invoke({"topic": topic, "run_id": run_id, "attempt": 0, "max_attempts": max_attempts,
                           "feedback": [], "historical_guidance": guidance, "rejection_history": [], "previous_failed": [], "status": "running"})
    except Exception:
        memory.finish_run(run_id, "error")
        raise

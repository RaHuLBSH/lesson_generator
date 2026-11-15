import json
from types import SimpleNamespace

from lesson_generator.evaluation.evaluator import LessonEvaluator

class FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])))

def payload(status="PASS"):
    names = ["accuracy_and_grounding", "beginner_friendly_language", "practical_examples", "clear_explanations_without_unexplained_jargon", "coverage_of_essential_concepts", "logical_teaching_flow"]
    result = {n: {"status": status, "explanation": "Reviewed", "evidence": "RAG uses retrieved context.", "failure_reasons": [], "correction_instruction": None} for n in names}
    result.update(overall_status=status, summary_of_required_improvements="")
    return json.dumps(result)

def lesson(extra=""):
    return """# Introduction\n## What RAG means\nRAG means retrieval augmented generation. It finds relevant documents and gives them to a language model.\n## Why it is needed\nIt can use a collection of documents.\n## How it works\nFirst search, then give passages to a model.\n## Main parts\nSearch and answer generation.\n## Practical use case\nA school can answer questions from its handbook.\n## Advantages and limitations\nIt can use local information, but bad search can give a wrong answer.\n## Recap\n## Step-by-step example\nStep 1: ask a question. Step 2: find a passage. Step 3: answer from it.\n""" + extra

def evaluate(text, response):
    return LessonEvaluator(client=FakeClient(response), model="fake", reference="RAG searches document passages and supplies them to a language model.").evaluate(text)

def test_good_lesson_passes_all():
    assert evaluate(lesson(), payload()).overall_status == "PASS"

def test_inaccurate_lesson_fails_accuracy():
    data = json.loads(payload()); data["accuracy_and_grounding"].update(status="FAIL", failure_reasons=["Contradicts reference"], correction_instruction="Correct claim")
    data["overall_status"] = "FAIL"
    assert evaluate(lesson(), json.dumps(data)).accuracy_and_grounding.status == "FAIL"

def test_unexplained_jargon_fails_relevant_criterion():
    data = json.loads(payload()); data["clear_explanations_without_unexplained_jargon"].update(status="FAIL", failure_reasons=["Embedding undefined"], correction_instruction="Define embedding")
    data["overall_status"] = "FAIL"
    assert evaluate(lesson("Embedding and vectorization."), json.dumps(data)).clear_explanations_without_unexplained_jargon.status == "FAIL"

def test_missing_example_fails_example_criterion():
    text = lesson().replace("## Step-by-step example\nStep 1: ask a question. Step 2: find a passage. Step 3: answer from it.", "## Step-by-step example\n")
    report = evaluate(text, payload())
    assert report.practical_examples.status == "FAIL"
    assert report.overall_status == "FAIL"

def test_malformed_response_fails_safely():
    report = evaluate(lesson(), "not json")
    assert report.overall_status == "FAIL"

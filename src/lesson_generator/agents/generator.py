"""Standalone lesson generation agent."""
from pathlib import Path
from ..llm import create_client, model_name
from ..schemas import LessonDocument

REFERENCE_PATH = Path(__file__).resolve().parents[3] / "references" / "rag_primer.md"

SYSTEM_PROMPT = """Write a complete standalone lesson for a learner with no technical background (Indian 12th-grade graduate, limited English). Use simple English and short sentences. Explain each technical term before using it. Include relatable analogies and a practical step-by-step example. Cover what the concept is, why needed, how it works, main components, practical use case, advantages, limitations, and recap. Use Markdown headings. Use only the supplied reference for factual claims. On revisions, follow evaluator feedback. Return only the lesson Markdown."""

class LessonGenerator:
    def __init__(self, client=None, model: str | None = None, reference: str | None = None):
        self.client = client or create_client()
        self.model = model or model_name()
        self.reference = reference if reference is not None else REFERENCE_PATH.read_text(encoding="utf-8")

    def generate(self, topic: str, feedback: list[str] | None = None, historical_guidance: list[str] | None = None) -> LessonDocument:
        revision = "\nPrevious evaluator feedback to address:\n" + "\n".join(feedback or [])
        revision += "\nHistorical guidance (advisory only; current topic, reference and rubric take priority):\n" + "\n".join(historical_guidance or [])
        response = self.client.chat.completions.create(model=self.model, temperature=0.2, messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Topic: {topic}\n\nReference:\n{self.reference}{revision}"},
        ])
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ValueError("The model returned an empty lesson")
        return LessonDocument(topic=topic, markdown=content.strip())

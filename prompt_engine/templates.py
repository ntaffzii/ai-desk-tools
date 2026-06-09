"""Prompt templates by task type."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    task_type: str
    system_prompt: str
    structure_hint: str


TEMPLATES: dict[str, PromptTemplate] = {
    "rag": PromptTemplate(
        "rag",
        "Improve the prompt for a RAG task. Require answers from provided sources only, citation when possible, and a fallback when information is missing.",
        "Role -> Sources -> Question -> Rules -> Output format",
    ),
    "code": PromptTemplate(
        "code",
        "Improve the prompt for a coding task. Clarify language, inputs, outputs, constraints, examples, and verification.",
        "Context -> Task -> Inputs -> Expected output -> Constraints -> Tests",
    ),
    "summary": PromptTemplate(
        "summary",
        "Improve the prompt for summarization. Clarify audience, length, focus, and output format.",
        "Audience -> Content -> Focus -> Length -> Output format",
    ),
    "extraction": PromptTemplate(
        "extraction",
        "Improve the prompt for structured extraction. Require exact schema, missing value behavior, and JSON-only output.",
        "Input -> Schema -> Rules -> JSON-only output",
    ),
    "translation": PromptTemplate(
        "translation",
        "Improve the prompt for translation. Clarify source/target language, tone, domain, and terms to preserve.",
        "Source -> Target -> Tone -> Domain -> Preserve",
    ),
    "analysis": PromptTemplate(
        "analysis",
        "Improve the prompt for analysis. Clarify framework, dimensions, evidence, and output sections.",
        "Subject -> Context -> Framework -> Dimensions -> Output",
    ),
    "creative": PromptTemplate(
        "creative",
        "Improve the prompt for creative writing. Clarify genre, tone, setting, constraints, and length.",
        "Genre -> Tone -> Elements -> Constraints -> Length",
    ),
    "qa": PromptTemplate(
        "qa",
        "Improve the prompt for question answering. Clarify question, audience, depth, and response structure.",
        "Question -> Context -> Audience -> Depth -> Format",
    ),
    "general": PromptTemplate(
        "general",
        "Improve the prompt to be clearer, more specific, and easier to answer well.",
        "Role -> Context -> Task -> Output format -> Constraints",
    ),
}


class TemplateSelector:
    def get(self, task_type: str) -> PromptTemplate:
        return TEMPLATES.get(task_type, TEMPLATES["general"])

    def get_system_prompt(self, task_type: str) -> str:
        return self.get(task_type).system_prompt

    def get_structure_hint(self, task_type: str) -> str:
        return self.get(task_type).structure_hint

    def list_task_types(self) -> list[str]:
        return list(TEMPLATES)

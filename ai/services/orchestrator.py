from .providers.mock import MockProvider
from .retrieval import search_legal_knowledge


class AIOrchestrator:
    """
    Coordinates retrieval and AI generation.

    The orchestrator deliberately knows nothing about HTTP requests.
    """

    def __init__(self, provider=None):
        self.provider = provider or MockProvider()

    def research(self, question, *, user=None, matter=None):
        context = search_legal_knowledge(question)

        system_prompt = (
            "You are AdvocateOS AI, a Kenyan legal research assistant. "
            "Use only the supplied legal sources when answering. "
            "Do not invent cases, statutes, citations, quotations, "
            "or procedural requirements."
        )

        user_prompt = question

        result = self.provider.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            context=context,
        )

        return {
            "question": question,
            "answer": result["content"],
            "provider": result["provider"],
            "model": result["model"],
            "sources": context,
        }
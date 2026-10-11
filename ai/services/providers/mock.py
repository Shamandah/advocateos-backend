from .base import AIProvider


class MockProvider(AIProvider):
    """
    Development provider.

    Does not call an external AI service.
    This allows the complete AI pipeline to be tested
    without API costs.
    """

    provider_name = "mock"
    model_name = "mock-v0.1"

    def generate(self, *, system_prompt, user_prompt, context):
        if not context:
            content = (
                "No verified legal sources were retrieved for this question. "
                "AdvocateOS AI cannot provide a source-backed legal answer yet."
            )
        else:
            source_lines = []

            for index, item in enumerate(context, start=1):
                source_lines.append(
                    f"[{index}] {item['title']}"
                    f"{' — ' + item['citation'] if item.get('citation') else ''}"
                )

            content = (
                "AdvocateOS AI Research v0.1\n\n"
                "The research pipeline retrieved the following verified "
                "legal knowledge sources for the question:\n\n"
                + "\n".join(source_lines)
                + "\n\n"
                "A language model will be connected in the next stage "
                "to synthesize a source-grounded answer."
            )

        return {
            "content": content,
            "provider": self.provider_name,
            "model": self.model_name,
        }
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """
    Provider interface for AdvocateOS AI.

    Implementations can use:
    - a local/self-hosted model
    - Claude
    - another external provider
    - a mock provider for testing
    """

    @abstractmethod
    def generate(self, *, system_prompt, user_prompt, context):
        """
        Generate an AI response.

        Returns:
            dict with at least:
            {
                "content": str,
                "model": str,
                "provider": str,
            }
        """
        raise NotImplementedError
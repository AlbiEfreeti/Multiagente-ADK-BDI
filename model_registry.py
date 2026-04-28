try:
    from typing import override
except ImportError:
    from typing_extensions import override

from google.adk.models.lite_llm import LiteLlm
from google.adk.models.registry import LLMRegistry


class OpenAiLiteLlm(LiteLlm):
    @classmethod
    @override
    def supported_models(cls):
        # Tiene que matchear EXACTAMENTE tu string "openai/gpt-oss-120b"
        return [r"openai/.*"]


LLMRegistry.register(OpenAiLiteLlm)

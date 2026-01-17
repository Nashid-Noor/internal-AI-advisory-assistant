
from abc import ABC, abstractmethod
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import LLMConnectionError, LLMRateLimitError
from app.core.logging import get_logger

logger = get_logger(__name__)


class LLMProvider(ABC):
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        pass
    
    @abstractmethod
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        pass


class OpenAIProvider(LLMProvider):
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.llm_model
        self.base_url = base_url
        
        if not self.api_key:
            raise LLMConnectionError(
                provider="openai",
                reason="API key not configured",
            )
        
        # Lazy import
        from openai import AsyncOpenAI
        
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
        
        logger.info(
            "OpenAI provider initialized",
            model=self.model,
        )
    
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.llm_timeout,
            )
            
            content = response.choices[0].message.content or ""
            
            # Log usage
            if response.usage:
                logger.debug(
                    "LLM usage",
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )
            
            return content
            
        except Exception as e:
            error_str = str(e).lower()
            
            if "rate limit" in error_str or "429" in error_str:
                logger.warning("Rate limit hit", error=str(e))
                raise LLMRateLimitError()
            
            logger.error(
                "LLM generation failed",
                error=str(e),
            )
            raise LLMConnectionError(
                provider="openai",
                reason=str(e),
            )
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json
        
        # Add JSON instruction to system prompt
        json_instruction = "\nYou must respond with valid JSON only. No markdown, no explanation."
        
        if system_prompt:
            system_prompt += json_instruction
        else:
            system_prompt = json_instruction
        
        if schema:
            system_prompt += f"\nJSON Schema: {json.dumps(schema)}"
        
        response = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0,  # More deterministic for JSON
        )
        
        # Clean and parse
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])
        
        return json.loads(cleaned)


class AzureOpenAIProvider(LLMProvider):
    
    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
    ) -> None:
        self.endpoint = endpoint or settings.azure_openai_endpoint
        self.api_key = api_key or settings.azure_openai_api_key
        self.deployment = deployment or settings.azure_openai_deployment
        
        if not all([self.endpoint, self.api_key, self.deployment]):
            raise LLMConnectionError(
                provider="azure",
                reason="Azure OpenAI configuration incomplete",
            )
        
        from openai import AsyncAzureOpenAI
        
        self.client = AsyncAzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version="2024-02-01",
        )
        
        logger.info(
            "Azure OpenAI provider initialized",
            deployment=self.deployment,
        )
    
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            return response.choices[0].message.content or ""
            
        except Exception as e:
            logger.error("Azure LLM generation failed", error=str(e))
            raise LLMConnectionError(provider="azure", reason=str(e))
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        import json
        
        json_instruction = "\nRespond with valid JSON only."
        if system_prompt:
            system_prompt += json_instruction
        else:
            system_prompt = json_instruction
        
        response = await self.generate(prompt, system_prompt, temperature=0)
        return json.loads(response.strip())


class LLMService:
    
    def __init__(self, provider: LLMProvider | None = None) -> None:
        if provider:
            self.provider = provider
        elif settings.llm_provider == "azure":
            self.provider = AzureOpenAIProvider()
        else:
            self.provider = OpenAIProvider()
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return await self.provider.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature or settings.llm_temperature,
            max_tokens=max_tokens or settings.llm_max_tokens,
        )
    
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return await self.provider.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            schema=schema,
        )


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

import abc
import json
import re
from typing import List, Dict, AsyncGenerator, Optional
import httpx
from backend.app.core.config import settings
from backend.app.core.errors import LLMUnavailableError


class LLMResponse:
    def __init__(
        self,
        content: str,
        evidence_status: str = "grounded",
        citations_used: Optional[List[str]] = None,
        tokens_used: int = 0,
    ):
        self.content = content
        self.evidence_status = evidence_status
        self.citations_used = citations_used or []
        self.tokens_used = tokens_used


class BaseLLMAdapter(abc.ABC):
    @abc.abstractmethod
    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        pass

    @abc.abstractmethod
    async def stream_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        pass


class MockLLMAdapter(BaseLLMAdapter):
    """Deterministic Grounded Generator for offline execution and tests."""
    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        user_msg = messages[-1]["content"] if messages else ""
        has_evidence = "Content:" in user_msg or "Source:" in user_msg
        
        if "No relevant college documents found" in user_msg or not has_evidence:
            answer = (
                "**Answer**:\n"
                "I'm sorry, but the official college knowledge base does not contain enough information to answer this question accurately.\n\n"
                "**Conditions / Next Actions**:\n"
                "- Please verify your question or consult the relevant college administrative office or official portal.\n\n"
                "**Evidence status**:\n"
                "Insufficient evidence"
            )
            return LLMResponse(content=answer, evidence_status="insufficient_evidence", citations_used=[], tokens_used=50)

        source_matches = re.findall(r"\[(\d+)\]\s+Source:\s+([^\n\)]+)", user_msg)
        citations = [f"[{m[0]}]" for m in source_matches] if source_matches else ["[1]"]

        content_blocks = re.findall(r"Content:\s*\n(.*?)(?=\n---|\n\[\d+\]|$)", user_msg, re.DOTALL)
        core_info = "According to the official college policy"
        if content_blocks:
            first_block = content_blocks[0].strip().replace("\n", " ")
            core_info = first_block[:280].rstrip(".")

        sources_text = "\n".join([f"{c} {m[1].strip()}" for c, m in zip(citations, source_matches)]) if source_matches else "[1] College Official Regulations"

        answer = (
            f"**Answer**:\n"
            f"- {core_info} {citations[0]}.\n"
            f"- All students and applicants are advised to review the latest official schedule and criteria.\n"
            f"- For further assistance, contact the respective department office or student desk.\n\n"
            f"**Sources**:\n"
            f"{sources_text}\n\n"
            f"**Evidence status**:\n"
            f"Grounded"
        )
        return LLMResponse(content=answer, evidence_status="grounded", citations_used=citations, tokens_used=120)

    async def stream_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        resp = self.generate(system_prompt, messages, temperature, max_tokens)
        for w in resp.content.split(" "):
            yield w + " "


class OpenAILLMAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"

    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMUnavailableError("LLM_API_KEY is not configured in .env")
        
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            with httpx.Client(timeout=45.0) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise LLMUnavailableError(f"OpenAI API Error: {resp.text}")
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                status = "grounded"
                if "insufficient evidence" in content.lower() or "does not contain" in content.lower():
                    status = "insufficient_evidence"
                
                citations = list(set(re.findall(r"\[\d+\]", content)))
                return LLMResponse(content=content, evidence_status=status, citations_used=citations, tokens_used=tokens)
        except Exception as e:
            if isinstance(e, LLMUnavailableError):
                raise e
            raise LLMUnavailableError(f"Failed to communicate with OpenAI: {str(e)}")

    async def stream_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        if not self.api_key:
            raise LLMUnavailableError("LLM_API_KEY is not configured in .env")
            
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = json.loads(line[6:])
                            delta = chunk["choices"][0].get("delta", {}).get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            continue


_gemini_llm_client: Optional[httpx.Client] = None


def _get_llm_client() -> httpx.Client:
    global _gemini_llm_client
    if _gemini_llm_client is None or _gemini_llm_client.is_closed:
        _gemini_llm_client = httpx.Client(
            timeout=35.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=120.0)
        )
    return _gemini_llm_client


class GeminiLLMAdapter(BaseLLMAdapter):
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model or "gemini-1.5-flash"

    def generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        if not self.api_key:
            raise LLMUnavailableError("LLM_API_KEY is not configured in .env")
        
        contents = []
        for m in messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
            
        model_name = self.model if self.model.startswith("models/") else f"models/{self.model}"
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={self.api_key}"
        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        try:
            client = _get_llm_client()
            try:
                resp = client.post(url, json=payload)
            except Exception:
                global _gemini_llm_client
                _gemini_llm_client = None
                client = _get_llm_client()
                resp = client.post(url, json=payload)

            if resp.status_code != 200:
                raise LLMUnavailableError(f"Gemini API error: {resp.text}")
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            status = "grounded"
            if "insufficient evidence" in text.lower() or "does not contain" in text.lower():
                status = "insufficient_evidence"
            citations = list(set(re.findall(r"\[\d+\]", text)))
            return LLMResponse(content=text, evidence_status=status, citations_used=citations, tokens_used=150)
        except Exception as e:
            if isinstance(e, LLMUnavailableError):
                raise e
            raise LLMUnavailableError(f"Gemini request failed: {str(e)}")

    async def stream_generate(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> AsyncGenerator[str, None]:
        resp = self.generate(system_prompt, messages, temperature, max_tokens)
        for w in resp.content.split(" "):
            yield w + " "


def get_llm_adapter() -> BaseLLMAdapter:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai" and settings.LLM_API_KEY:
        return OpenAILLMAdapter(api_key=settings.LLM_API_KEY, model=settings.LLM_MODEL)
    elif provider == "gemini" and settings.LLM_API_KEY:
        return GeminiLLMAdapter(api_key=settings.LLM_API_KEY, model=settings.LLM_MODEL)
    return MockLLMAdapter()

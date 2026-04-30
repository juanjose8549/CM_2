"""
LLM Client abstraction for the AI Agent.
Supports OpenAI and Anthropic with function calling/tool use.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
import json
import os


class LLMClient(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Send a chat completion request to the LLM.
        
        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tools/functions for function calling
            temperature: Response randomness (0-1)
            max_tokens: Maximum tokens in response
        
        Returns:
            Dict with 'content' (str) and optionally 'tool_calls' (list)
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name being used."""
        pass


class OpenAIClient(LLMClient):
    """OpenAI GPT-4 client with function calling support."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", base_url: Optional[str] = None):
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package not installed. Run: pip install openai"
            )
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY not found. Set it in .env or pass it to the constructor."
            )
        
        client_kwargs = {"api_key": self.api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Send a chat completion with optional function calling.
        
        Returns:
            Dict with:
            - 'content': Response text (may be None if tool_call)
            - 'tool_calls': List of tool calls (may be empty)
            - 'finish_reason': 'stop', 'tool_calls', or 'length'
        """
        kwargs = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)
            
            message = response.choices[0].message
            
            result = {
                "content": message.content or "",
                "tool_calls": [],
                "finish_reason": response.choices[0].finish_reason
            }

            # Process tool calls
            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    result["tool_calls"].append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": arguments
                        }
                    })

            return result

        except Exception as e:
            # Fall back to a simple completion if tool calling fails
            if "tool" in str(e).lower():
                kwargs.pop("tools", None)
                kwargs.pop("tool_choice", None)
                response = await self.client.chat.completions.create(**kwargs)
                return {
                    "content": response.choices[0].message.content or "",
                    "tool_calls": [],
                    "finish_reason": "stop"
                }
            raise


class AnthropicClient(LLMClient):
    """Anthropic Claude client with tool use support."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-opus-20240229"):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Anthropic package not installed. Run: pip install anthropic"
            )
        
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. Set it in .env or pass it to the constructor."
            )
        
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        return self._model

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Send a message to Claude with optional tool use.
        
        Note: Anthropic uses a different tool format. This method
        converts from OpenAI format internally.
        """
        # Convert messages to Anthropic format
        anthropic_messages = []
        system_content = None
        
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            
            if role == "system":
                system_content = content
                continue
            elif role == "function":
                # Convert function results to 'tool_result' content
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("name", "unknown"),
                            "content": content
                        }
                    ]
                })
                continue
            
            anthropic_messages.append({"role": role, "content": content})

        # Convert tools to Anthropic format
        anthropic_tools = None
        if tools:
            anthropic_tools = []
            for tool in tools:
                func = tool.get("function", tool)
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {})
                })

        try:
            kwargs = {
                "model": self._model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            
            if system_content:
                kwargs["system"] = system_content
            
            if anthropic_tools:
                kwargs["tools"] = anthropic_tools

            response = await self.client.messages.create(**kwargs)
            
            result = {
                "content": "",
                "tool_calls": [],
                "finish_reason": "stop"
            }

            # Process response content blocks
            for block in response.content:
                if block.type == "text":
                    result["content"] += block.text
                elif block.type == "tool_use":
                    result["tool_calls"].append({
                        "id": block.id,
                        "type": "function",
                        "function": {
                            "name": block.name,
                            "arguments": block.input
                        }
                    })
                    result["finish_reason"] = "tool_calls"

            return result

        except Exception as e:
            raise


def create_llm_client(provider: str = "openai", **kwargs) -> LLMClient:
    """
    Factory function to create an LLM client.
    
    Args:
        provider: 'openai', 'anthropic', or 'deepseek'
        **kwargs: Additional args passed to the client constructor
    
    Returns:
        LLMClient instance
    
    Raises:
        ValueError: If provider is unknown
    """
    providers = {
        "openai": OpenAIClient,
        "anthropic": AnthropicClient,
    }
    
    provider_lower = provider.lower()
    
    # DeepSeek uses OpenAI-compatible API, just needs different base_url
    if provider_lower == "deepseek":
        kwargs.setdefault("base_url", "https://api.deepseek.com")
        kwargs.setdefault("model", "deepseek-chat")
        # DeepSeek API key should be in DEEPSEEK_API_KEY or OPENAI_API_KEY
        key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if key:
            kwargs["api_key"] = key
        return OpenAIClient(**kwargs)
    
    if provider_lower not in providers:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Available: openai, anthropic, deepseek"
        )
    
    return providers[provider_lower](**kwargs)

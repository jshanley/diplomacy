# ==============================================================================
# Copyright (C) 2019 - Philip Paquette
#
#  This program is free software: you can redistribute it and/or modify it under
#  the terms of the GNU Affero General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any
#  later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
#  FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
#  details.
#
#  You should have received a copy of the GNU Affero General Public License along
#  with this program.  If not, see <https://www.gnu.org/licenses/>.
# ==============================================================================
"""Model-agnostic LLM provider abstraction for Diplomacy agents."""
from abc import ABCMeta, abstractmethod


class LLMProvider(metaclass=ABCMeta):
    """Abstract interface for LLM completions.

    Subclasses wrap a specific LLM API (OpenAI, Anthropic, etc.) behind a
    uniform ``complete(system_prompt, user_message) -> str`` interface.
    """

    @abstractmethod
    def complete(self, system_prompt, user_message):
        """Send a prompt to the LLM and return the response text.

        :param system_prompt: System-level instructions for the model.
        :param user_message: The user/game-state message.
        :type system_prompt: str
        :type user_message: str
        :return: Model response text.
        :rtype: str
        """

    @property
    def model(self):
        """Return the model identifier string."""
        return getattr(self, '_model', 'unknown')


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------

class OpenAIProvider(LLMProvider):
    """LLM provider using the OpenAI API (ChatCompletion)."""

    def __init__(self, api_key, model='gpt-4o', temperature=0.7, base_url=None):
        try:
            import openai  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise ImportError(
                'OpenAI SDK not installed. Run: pip install openai') from None
        kwargs = {'api_key': api_key}
        if base_url:
            kwargs['base_url'] = base_url
        self._client = openai.OpenAI(**kwargs)
        self._model = model
        self._temperature = temperature

    def complete(self, system_prompt, user_message):
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message},
            ],
            temperature=self._temperature,
        )
        return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------

class AnthropicProvider(LLMProvider):
    """LLM provider using the Anthropic Messages API."""

    def __init__(self, api_key, model='claude-sonnet-4-20250514', temperature=0.7,
                 max_tokens=4096):
        try:
            import anthropic  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise ImportError(
                'Anthropic SDK not installed. Run: pip install anthropic') from None
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens

    def complete(self, system_prompt, user_message):
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_message}],
            temperature=self._temperature,
        )
        return response.content[0].text


# ---------------------------------------------------------------------------
# Google (Gemini)
# ---------------------------------------------------------------------------

class GoogleProvider(LLMProvider):
    """LLM provider using the Google GenAI SDK (Gemini)."""

    def __init__(self, api_key, model='gemini-2.0-flash', temperature=0.7):
        try:
            from google import genai  # pylint: disable=import-outside-toplevel
        except ImportError:
            raise ImportError(
                'Google GenAI SDK not installed. Run: pip install google-genai') from None
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._temperature = temperature

    def complete(self, system_prompt, user_message):
        from google.genai import types  # pylint: disable=import-outside-toplevel
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=self._temperature,
            ),
        )
        return response.text


# ---------------------------------------------------------------------------
# Grok (xAI) — OpenAI-compatible API
# ---------------------------------------------------------------------------

class GrokProvider(OpenAIProvider):
    """LLM provider for xAI's Grok (OpenAI-compatible API)."""

    def __init__(self, api_key, model='grok-3-latest', temperature=0.7):
        super().__init__(
            api_key=api_key,
            model=model,
            temperature=temperature,
            base_url='https://api.x.ai/v1',
        )


# ---------------------------------------------------------------------------
# Stub (for testing)
# ---------------------------------------------------------------------------

class StubProvider(LLMProvider):
    """Testing stub that returns canned responses.

    Accepts either a list of response strings (returned in order) or a
    callable ``(system_prompt, user_message) -> str``.
    """

    def __init__(self, responses=None):
        self._model = 'stub'
        if callable(responses):
            self._fn = responses
            self._responses = None
        else:
            self._fn = None
            self._responses = list(responses) if responses else []
        self.call_count = 0
        self.last_system_prompt = None
        self.last_user_message = None

    def complete(self, system_prompt, user_message):
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        self.call_count += 1

        if self._fn is not None:
            return self._fn(system_prompt, user_message)
        if self._responses:
            return self._responses.pop(0)
        return ''

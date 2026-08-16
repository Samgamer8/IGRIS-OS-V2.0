"""Centralized strict JSON parser for IGRIS OS V2.0."""

import json
import re
from functools import lru_cache


class StrictJSONParser:
    """Strict JSON extractor with auto-repair and LRU caching."""

    @staticmethod
    def _fix_unescaped_newlines(text: str) -> str:
        in_string = False
        escape = False
        result = []
        for char in text:
            if escape:
                result.append(char)
                escape = False
            elif char == "\\" and in_string:
                result.append(char)
                escape = True
            elif char == '"':
                result.append(char)
                in_string = not in_string
            elif char in "\n\r" and in_string:
                result.append("\\n" if char == "\n" else "\\r")
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    @lru_cache(maxsize=128)
    def extract(text: str) -> dict:
        """Extract the first valid JSON object from the input text.

        Supports fenced code blocks (```json ... ``` and ``` ... ```),
        raw JSON objects, trailing commas, and unescaped newlines.

        Args:
            text: Input string potentially containing JSON.

        Returns:
            Parsed dictionary.

        Raises:
            TypeError: If text is not a string.
            ValueError: If no valid JSON object is found.
        """
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fenced:
            candidate = fenced.group(1).strip()
        else:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                raise ValueError("No JSON object found in text")
            candidate = match.group(0)

        candidate = StrictJSONParser._fix_unescaped_newlines(candidate)
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

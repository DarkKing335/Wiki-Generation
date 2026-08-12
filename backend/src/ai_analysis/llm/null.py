"""No-LLM fallback (US-3.2, FR-9).

*"As a user, I want RepoAtlas to work without an LLM, so that I can still
generate documentation."*  Acceptance: structural documentation is generated and
missing AI descriptions do not interrupt execution.

This client never calls a model and never raises.  It composes a description from
the structural facts already present in the prompt — the annotations, signatures
and inheritance the skeleton renderer put there.  The result is plainer than
generated prose but factually grounded by construction, since every word is
copied from the AST rather than predicted.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from ai_analysis.llm.base import LLMClient, LLMResponse

#: Annotations that reveal a type's architectural role, mapped to plain English.
ROLE_BY_ANNOTATION = {
    # Java / Spring
    "RestController": "a REST controller",
    "Controller": "a web controller",
    "Service": "a service component",
    "Repository": "a persistence repository",
    "Component": "a Spring-managed component",
    "Entity": "a persistence entity",
    "Configuration": "a configuration class",
    "Test": "a test case",
    # C# / ASP.NET
    "ApiController": "an API controller",
    "Fact": "a test case",
    "Theory": "a parameterised test case",
    "TestMethod": "a test case",
}

_CLASS_HEADER = re.compile(r"^(Class|Interface|Enum|Record|Struct): (\S+)", re.MULTILINE)
_METHOD_LINE = re.compile(r"^\s*\*\s+(.+)$", re.MULTILINE)
_DOC_LINE = re.compile(r"^\s*Doc: (.+)$", re.MULTILINE)
_IMPLEMENTS = re.compile(r"implements ([\w., ]+)")
_EXTENDS = re.compile(r"extends (\w+)")
_DIGEST_LINE = re.compile(r"^- ([^:]+): (.+)$", re.MULTILINE)


class NullLLMClient(LLMClient):
    """Produces structural descriptions without invoking any model."""

    name = "structural"
    enabled = False

    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        return LLMResponse(text=self._describe(prompt), model=None)

    # ------------------------------------------------------------------

    def _describe(self, prompt: str) -> str:
        """Compose a description from whatever structure the prompt carries."""
        # Aggregating tiers receive a child-summary digest.
        children = _DIGEST_LINE.findall(prompt)
        if children and not _CLASS_HEADER.search(prompt):
            return self._describe_aggregate(children)

        header = _CLASS_HEADER.search(prompt)
        if header:
            return self._describe_type(prompt, kind=header.group(1), name=header.group(2))

        return self._describe_method(prompt)

    def _describe_type(self, prompt: str, kind: str, name: str) -> str:
        parts: List[str] = []

        roles = [
            description
            for annotation, description in ROLE_BY_ANNOTATION.items()
            if f"@{annotation}" in prompt
        ]
        if roles:
            parts.append(f"{name} is {roles[0]}.")
        else:
            parts.append(f"{name} is {'an' if kind[0] in 'AEIOU' else 'a'} {kind.lower()}.")

        implements = _IMPLEMENTS.search(prompt)
        extends = _EXTENDS.search(prompt)
        if implements:
            parts.append(f"It implements {implements.group(1).strip()}.")
        if extends:
            parts.append(f"It extends {extends.group(1)}.")

        methods = _METHOD_LINE.findall(prompt)
        if methods:
            names = [self._method_name(m) for m in methods]
            shown = ", ".join(names[:6])
            more = f" and {len(names) - 6} more" if len(names) > 6 else ""
            parts.append(f"It declares {len(names)} member(s): {shown}{more}.")

        docs = _DOC_LINE.findall(prompt)
        if docs:
            parts.append(f"Documented intent: {docs[0]}")

        return " ".join(parts)

    def _describe_method(self, prompt: str) -> str:
        parts: List[str] = []

        methods = _METHOD_LINE.findall(prompt)
        if methods:
            signature = methods[0].strip()
            parts.append(f"Signature: {signature}.")

        docs = _DOC_LINE.findall(prompt)
        if docs:
            parts.append(docs[0])

        if not parts:
            parts.append("No structural detail available for this symbol.")

        return " ".join(parts)

    def _describe_aggregate(self, children: List[tuple]) -> str:
        names = [name.strip() for name, _ in children]
        shown = ", ".join(names[:8])
        more = f", and {len(names) - 8} more" if len(names) > 8 else ""
        return f"Groups {len(names)} element(s): {shown}{more}."

    @staticmethod
    def _method_name(signature: str) -> str:
        """Reduce a rendered signature to its bare name."""
        cleaned = signature.strip().lstrip("*").strip()
        cleaned = cleaned.removeprefix("async ").strip()
        return cleaned.split("(")[0].strip()

"""Tool harness — registry, definitions and dispatcher.

Implements the lazy source-loading handshake in ``docs/designs/ast-parser-design.md``
§8, where the SLM *requests* a method body rather than receiving it unconditionally.

This is a registry plus dispatcher, deliberately **not** an agent loop:
``docs/vision.md`` lists agent orchestration as out of scope and mandates
single-shot analysis.
"""

from __future__ import annotations

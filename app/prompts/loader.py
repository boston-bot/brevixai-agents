"""Prompt template loader with versioning, hashing, and safe variable interpolation."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent

# Strict name/version validation — these patterns are the path traversal defence.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_VERSION_RE = re.compile(r"^v\d+$")
_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


class PromptNotFoundError(FileNotFoundError):
    """Raised when a requested prompt template does not exist on disk."""


@dataclass(frozen=True)
class PromptTemplate:
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    _body: str

    def render(self, variables: dict[str, str]) -> str:
        """Return prompt text with {{variable}} placeholders substituted."""
        def _replace(match: re.Match) -> str:
            key = match.group(1)
            if key not in variables:
                raise KeyError(f"Missing prompt variable: {key!r}")
            return str(variables[key])

        return _VAR_RE.sub(_replace, self._body)

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "prompt_name": self.prompt_name,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
        }


def load_prompt(name: str, version: str) -> PromptTemplate:
    """Load a versioned prompt template by name and version.

    Path traversal is blocked by strict regex validation of name and version
    before any filesystem access.

    Raises PromptNotFoundError if the template file does not exist.
    """
    if not _NAME_RE.match(name):
        raise ValueError(f"Invalid prompt name: {name!r}")
    if not _VERSION_RE.match(version):
        raise ValueError(f"Invalid prompt version: {version!r}")

    path = (_PROMPTS_DIR / f"{name}.{version}.md").resolve()
    prompts_root = _PROMPTS_DIR.resolve()

    # Belt-and-suspenders: resolved path must stay inside prompts directory.
    if not str(path).startswith(str(prompts_root) + "/"):
        raise PromptNotFoundError(f"Prompt not found: {name}/{version}")

    if not path.exists():
        raise PromptNotFoundError(f"Prompt not found: {name}/{version}")

    raw = path.read_text(encoding="utf-8")
    prompt_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    body = _strip_frontmatter(raw).strip()

    return PromptTemplate(
        prompt_name=name,
        prompt_version=version,
        prompt_hash=prompt_hash,
        _body=body,
    )


def _strip_frontmatter(text: str) -> str:
    """Remove YAML-style --- frontmatter block from template text."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 4)
    if end == -1:
        return text
    return text[end + 5:]


# Canonical list of all prompt templates active in the graph.
# Update this when adding or bumping a prompt version.
PROMPT_REGISTRY: list[tuple[str, str]] = [
    ("router", "v1"),
    ("fraud_analyzer_summary", "v1"),
    ("investigation_synthesis", "v1"),
    ("explanation", "v1"),
    ("action_gate", "v1"),
]


def collect_prompt_metadata() -> list[dict[str, str]]:
    """Return metadata for every prompt in PROMPT_REGISTRY.

    Called by the report generator so benchmark reports always document
    which prompt versions produced the results.
    """
    return [load_prompt(name, version).metadata for name, version in PROMPT_REGISTRY]

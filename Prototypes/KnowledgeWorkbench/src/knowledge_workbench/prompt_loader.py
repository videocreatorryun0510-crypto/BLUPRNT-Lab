"""Load versioned prompts without embedding them in provider code."""

from pathlib import Path
from typing import Literal

PROMPT_VERSION: Literal["knowledge_generation_v0.3"] = "knowledge_generation_v0.3"


def load_knowledge_prompt() -> str:
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    base_prompt = (prompts_dir / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")
    test_item_template = (prompts_dir / "templates" / "test_item_v0.3.md").read_text(
        encoding="utf-8"
    )
    return f"{base_prompt}\n\n{test_item_template}"

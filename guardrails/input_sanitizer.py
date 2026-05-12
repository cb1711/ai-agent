import re

INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I), "instruction_override"),
    (re.compile(r"(disregard|forget|override)\s+(your\s+)?(system\s+)?(prompt|instructions?)", re.I), "instruction_override"),
    (re.compile(r"you\s+are\s+now\s+(?!an?\s+(AI|assistant))", re.I), "persona_hijack"),
    (re.compile(r"(new\s+)?system\s*(message|prompt)\s*:", re.I), "fake_system_prompt"),
    (re.compile(r"<\s*system\s*>", re.I), "fake_system_prompt"),
    (re.compile(r"\[INST\]|\[\/INST\]|<<SYS>>|<</SYS>>"), "llm_delimiter_injection"),
    (re.compile(r"(?<!\w)(human|assistant)\s*:\s*(?=\S)", re.I), "role_spoofing"),
]


class InputSanitizationError(ValueError):
    def __init__(self, label: str, snippet: str) -> None:
        super().__init__(label)
        self.label = label
        self.snippet = snippet


def sanitize_input(content: str) -> None:
    """Scan content for prompt injection patterns. Raises InputSanitizationError on match."""
    for pattern, label in INJECTION_PATTERNS:
        match = pattern.search(content)
        if match:
            raise InputSanitizationError(label, match.group(0)[:80])

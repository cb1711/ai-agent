import re
from dataclasses import dataclass


@dataclass
class OutputWarning:
    label: str
    snippet: str


_OUTPUT_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Injection chains embedded in agent output
    (re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.I), "output_injection"),
    (re.compile(r"<\s*system\s*>", re.I), "fake_system_in_output"),
    (re.compile(r"\[INST\]|\[\/INST\]|<<SYS>>", re.I), "llm_delimiter_in_output"),
    # Hallucinated actions — agent claims it took an action without using a tool
    (re.compile(r"\bI\s+(have\s+)?(just\s+)?sent\s+(an?\s+)?email\b", re.I), "hallucinated_email"),
    (re.compile(r"\bI\s+(have\s+)?(just\s+)?deleted\b", re.I), "hallucinated_delete"),
    (re.compile(r"\bI\s+(have\s+)?(just\s+)?(executed|ran?)\b.{0,40}(command|script|code)", re.I), "hallucinated_exec"),
]


def validate_output(response_text: str) -> list[OutputWarning]:
    """Return warnings for suspicious patterns in agent output. Never raises."""
    warnings = []
    for pattern, label in _OUTPUT_PATTERNS:
        match = pattern.search(response_text)
        if match:
            warnings.append(OutputWarning(label=label, snippet=match.group(0)[:80]))
    return warnings

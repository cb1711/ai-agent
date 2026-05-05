from langchain_core.tools import tool

from memory.store import recall_facts, remember_fact


@tool
def remember_fact_tool(key: str, value: str) -> str:
    """Persistently remember a fact as a key-value pair across sessions.
    Use when the user explicitly asks you to remember something.
    Examples: key='user_name', value='Alice' or key='preferred_language', value='Python'"""
    remember_fact(key, value)
    return f"Remembered: {key} = {value}"


@tool
def recall_facts_tool(query: str = "") -> str:
    """Recall stored facts. Pass a search term to filter, or empty string to get all facts.
    Use this before answering questions about things you should have been told previously."""
    facts = recall_facts(query)
    if not facts:
        return "No facts found." if query else "No facts stored yet."
    return "\n".join(f"- {k}: {v}" for k, v in facts.items())

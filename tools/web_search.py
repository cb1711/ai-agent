from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun

_search = DuckDuckGoSearchRun()


@tool
def web_search_tool(query: str) -> str:
    """Search the web using DuckDuckGo and return a summary of the top results.
    Use for current events, factual lookups, or anything you don't know."""
    try:
        return _search.run(query)
    except Exception as e:
        return f"Search failed: {e}"

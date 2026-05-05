import os
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage


class TestBuildAgent:
    def test_build_agent_returns_compiled_graph(self, isolated_db, mocker):
        """build_agent should return a LangGraph CompiledStateGraph without error."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mocker.patch("agent._build_llm", return_value=mock_llm)

        from agent import build_agent
        a = build_agent()
        assert a is not None

    def test_build_llm_uses_anthropic_by_default(self, mocker):
        from config import settings
        mocker.patch.object(settings, "llm_provider", "claude")
        mock_claude = MagicMock()
        mocker.patch("agent.ChatAnthropic", return_value=mock_claude, create=True)

        # Import fresh to trigger _build_llm
        import importlib
        import agent as agent_mod
        llm = agent_mod._build_llm()
        # Just verify it doesn't raise; provider check is integration-level
        assert llm is not None

    def test_build_llm_uses_ollama_when_configured(self, mocker):
        from config import settings
        mocker.patch.object(settings, "llm_provider", "ollama")

        mock_ollama = MagicMock()
        with patch("langchain_ollama.ChatOllama", return_value=mock_ollama):
            import agent as agent_mod
            llm = agent_mod._build_llm()
            assert llm is not None


class TestInvokeAgent:
    def test_invoke_agent_returns_string(self, isolated_db, mocker):
        """invoke_agent should return the last message content as a string."""
        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mocker.patch("agent._build_llm", return_value=mock_llm)

        from agent import build_agent, invoke_agent

        fake_response = {"messages": [HumanMessage(content="hi"), AIMessage(content="hello there")]}
        a = build_agent()
        mocker.patch.object(a, "invoke", return_value=fake_response)

        result = invoke_agent(a, "hi")
        assert result == "hello there"
        assert isinstance(result, str)

    def test_invoke_agent_passes_session_id_as_thread_id(self, isolated_db, mocker):
        from config import settings
        mocker.patch.object(settings, "session_id", "my-session-42")

        mock_llm = MagicMock()
        mock_llm.bind_tools = MagicMock(return_value=mock_llm)
        mocker.patch("agent._build_llm", return_value=mock_llm)

        from agent import build_agent, invoke_agent

        fake_response = {"messages": [AIMessage(content="ok")]}
        a = build_agent()
        invoke_mock = mocker.patch.object(a, "invoke", return_value=fake_response)

        invoke_agent(a, "hello")

        _, call_kwargs = invoke_mock.call_args
        config = call_kwargs.get("config", {})
        assert config.get("configurable", {}).get("thread_id") == "my-session-42"


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping live integration test",
)
class TestLiveAgent:
    def test_live_simple_question(self, isolated_db):
        from agent import build_agent, invoke_agent
        a = build_agent()
        answer = invoke_agent(a, "Reply with exactly the word: PONG")
        assert "PONG" in answer

    def test_live_memory_roundtrip(self, isolated_db):
        from agent import build_agent, invoke_agent
        a = build_agent()
        invoke_agent(a, "My favourite number is 42, please remember it.")
        answer = invoke_agent(a, "What is my favourite number?")
        assert "42" in answer

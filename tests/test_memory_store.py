import pytest
from memory.store import remember_fact, recall_facts


def test_remember_and_recall_single_fact(isolated_db):
    remember_fact("name", "Alice")
    assert recall_facts()["name"] == "Alice"


def test_recall_returns_all_facts(isolated_db):
    remember_fact("lang", "Python")
    remember_fact("editor", "neovim")
    facts = recall_facts()
    assert facts["lang"] == "Python"
    assert facts["editor"] == "neovim"


def test_recall_filters_by_query(isolated_db):
    remember_fact("favourite_food", "pizza")
    remember_fact("favourite_color", "blue")
    remember_fact("project", "agent")
    results = recall_facts("favourite")
    assert "favourite_food" in results
    assert "favourite_color" in results
    assert "project" not in results


def test_recall_query_matches_value(isolated_db):
    remember_fact("config", "use_dark_mode=true")
    results = recall_facts("dark_mode")
    assert "config" in results


def test_overwrite_key(isolated_db):
    remember_fact("version", "1.0")
    remember_fact("version", "2.0")
    assert recall_facts()["version"] == "2.0"


def test_key_is_lowercased(isolated_db):
    remember_fact("USER_NAME", "Bob")
    assert "user_name" in recall_facts()
    assert "USER_NAME" not in recall_facts()


def test_recall_empty_db(isolated_db):
    assert recall_facts() == {}


def test_recall_no_query_match(isolated_db):
    remember_fact("animal", "cat")
    assert recall_facts("dragon") == {}

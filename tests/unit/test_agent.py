"""Tests for agent definition parsing and template rendering."""

import tempfile
from pathlib import Path

import pytest


class TestRenderTemplate:
    """A4: Agent body template rendering with {{param}} placeholders."""

    def test_render_single_param(self):
        from loopflow.agent import render_template
        body = "Translate to {{language}}."
        result = render_template(body, language="Chinese")
        assert result == "Translate to Chinese."

    def test_render_multiple_params(self):
        from loopflow.agent import render_template
        body = "You are a {{role}}. Output in {{format}}."
        result = render_template(body, role="translator", format="JSON")
        assert result == "You are a translator. Output in JSON."

    def test_render_no_params(self):
        from loopflow.agent import render_template
        body = "You are a helpful assistant."
        result = render_template(body)
        assert result == "You are a helpful assistant."

    def test_render_missing_param_raises(self):
        from loopflow.agent import render_template
        body = "Translate to {{language}}."
        with pytest.raises(ValueError, match="language"):
            render_template(body)

    def test_render_duplicate_param(self):
        from loopflow.agent import render_template
        body = "{{name}} says: {{name}} is here."
        result = render_template(body, name="Alice")
        assert result == "Alice says: Alice is here."

    def test_render_extra_kwargs_ignored(self):
        from loopflow.agent import render_template
        body = "Hello {{name}}."
        result = render_template(body, name="Alice", extra="ignored")
        assert result == "Hello Alice."

    def test_render_empty_body(self):
        from loopflow.agent import render_template
        result = render_template("")
        assert result == ""


class TestParseAgent:
    """Existing agent definition parsing tests."""

    def test_parse_valid_agent(self):
        from loopflow.agent import parse_agent
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test-agent
description: A test agent
---
You are a test agent.""")
            f.flush()
            result = parse_agent(f.name)
            assert result.name == "test-agent"
            assert result.description == "A test agent"

    def test_parse_agent_with_requires(self):
        from loopflow.agent import parse_agent
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test-agent
description: A test agent with requirements
requires:
  env:
    - API_KEY
  params:
    - language
    - format
  mcps:
    - filesystem
---
You are a test agent. Output in {{language}}.""")
            f.flush()
            result = parse_agent(f.name)
            assert result.name == "test-agent"
            assert result.requires is not None
            assert result.requires.env == ["API_KEY"]
            assert result.requires.params == ["language", "format"]
            assert result.requires.mcps == ["filesystem"]

    def test_parse_agent_missing_name(self):
        from loopflow.agent import parse_agent
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
description: Missing name
---
body""")
            f.flush()
            with pytest.raises(ValueError, match="name"):
                parse_agent(f.name)

    def test_parse_agent_missing_file(self):
        from loopflow.agent import parse_agent
        with pytest.raises(FileNotFoundError):
            parse_agent("/nonexistent/agent.md")
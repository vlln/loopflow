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


class TestResolveParams:
    """Resolve template parameters with defaults."""

    def test_required_provided(self):
        from loopflow.agent import ParamSpec, resolve_params
        params = [ParamSpec("language")]
        result = resolve_params(params, language="Chinese")
        assert result == {"language": "Chinese"}

    def test_required_missing_raises(self):
        from loopflow.agent import ParamSpec, resolve_params
        params = [ParamSpec("language")]
        with pytest.raises(ValueError, match="language"):
            resolve_params(params)

    def test_optional_with_default(self):
        from loopflow.agent import ParamSpec, resolve_params
        params = [ParamSpec("language", required=False, default="English")]
        result = resolve_params(params)
        assert result == {"language": "English"}

    def test_optional_overridden(self):
        from loopflow.agent import ParamSpec, resolve_params
        params = [ParamSpec("language", required=False, default="English")]
        result = resolve_params(params, language="Chinese")
        assert result == {"language": "Chinese"}

    def test_mixed_required_and_optional(self):
        from loopflow.agent import ParamSpec, resolve_params
        params = [
            ParamSpec("language"),  # required
            ParamSpec("format", required=False, default="markdown"),
            ParamSpec("figure_mode", required=False, default="generate"),
        ]
        result = resolve_params(params, language="Chinese")
        assert result == {
            "language": "Chinese",
            "format": "markdown",
            "figure_mode": "generate",
        }

    def test_extra_kwargs_passthrough(self):
        from loopflow.agent import ParamSpec, resolve_params
        params = [ParamSpec("language")]
        result = resolve_params(params, language="Chinese", extra="ignored")
        assert result == {"language": "Chinese", "extra": "ignored"}

    def test_no_params(self):
        from loopflow.agent import resolve_params
        result = resolve_params(None, language="Chinese")
        assert result == {"language": "Chinese"}


class TestParseAgentParams:
    """Parse agent definition with new param format."""

    def test_old_format_params(self):
        """Backward compatible: - param_name (required)."""
        import tempfile
        from loopflow.agent import parse_agent
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test
description: Test agent
requires:
  params:
    - language
    - format
---
body""")
            f.flush()
            result = parse_agent(f.name)
            assert result.requires is not None
            assert len(result.requires.params) == 2
            assert result.requires.params[0].name == "language"
            assert result.requires.params[0].required is True
            assert result.requires.params[1].name == "format"
            assert result.requires.params[1].required is True

    def test_new_format_params(self):
        """New format: - param_name: default_value (optional)."""
        import tempfile
        from loopflow.agent import parse_agent
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test
description: Test agent
requires:
  params:
    - language
    - format: markdown
    - figure_mode: generate
---
body""")
            f.flush()
            result = parse_agent(f.name)
            assert result.requires is not None
            assert len(result.requires.params) == 3
            assert result.requires.params[0].name == "language"
            assert result.requires.params[0].required is True
            assert result.requires.params[1].name == "format"
            assert result.requires.params[1].required is False
            assert result.requires.params[1].default == "markdown"
            assert result.requires.params[2].name == "figure_mode"
            assert result.requires.params[2].required is False
            assert result.requires.params[2].default == "generate"


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
            assert len(result.requires.params) == 2
            assert result.requires.params[0].name == "language"
            assert result.requires.params[0].required is True
            assert result.requires.params[1].name == "format"
            assert result.requires.params[1].required is True
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
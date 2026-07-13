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


class TestParseAgentInput:
    """Parse agent definition with input schema (JSON Schema)."""

    def test_input_required_params(self):
        """input with required params."""
        import tempfile
        from loopflow.agent import parse_agent, _input_to_params
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test
description: Test agent
input:
  type: object
  properties:
    language:
      type: string
    format:
      type: string
  required:
    - language
    - format
---
body""")
            f.flush()
            result = parse_agent(f.name)
            assert result.input is not None
            assert result.input["type"] == "object"
            params = _input_to_params(result.input)
            assert len(params) == 2
            assert params[0].name == "language"
            assert params[0].required is True
            assert params[1].name == "format"
            assert params[1].required is True

    def test_input_with_defaults(self):
        """input with optional params that have defaults."""
        import tempfile
        from loopflow.agent import parse_agent, _input_to_params
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test
description: Test agent
input:
  type: object
  properties:
    language:
      type: string
    format:
      type: string
      default: markdown
    figure_mode:
      type: string
      default: generate
  required:
    - language
---
body""")
            f.flush()
            result = parse_agent(f.name)
            params = _input_to_params(result.input)
            assert len(params) == 3
            assert params[0].name == "language"
            assert params[0].required is True
            assert params[1].name == "format"
            assert params[1].required is False
            assert params[1].default == "markdown"
            assert params[2].name == "figure_mode"
            assert params[2].required is False
            assert params[2].default == "generate"

    def test_input_with_enum(self):
        """input with enum values."""
        import tempfile
        from loopflow.agent import parse_agent, _input_to_params
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test
description: Test agent
input:
  type: object
  properties:
    mode:
      type: string
      enum: [generate, extract]
      default: generate
  required:
    - mode
---
body""")
            f.flush()
            result = parse_agent(f.name)
            params = _input_to_params(result.input)
            assert len(params) == 1
            assert params[0].name == "mode"
            assert params[0].required is False  # has default, so not required
            assert params[0].default == "generate"

    def test_input_none(self):
        """Agents without input field have input=None."""
        import tempfile
        from loopflow.agent import parse_agent, _input_to_params
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: simple
description: Simple agent
---
Just a body.""")
            f.flush()
            result = parse_agent(f.name)
            assert result.input is None
            assert _input_to_params(result.input) == []

    def test_input_not_dict_ignored(self):
        """input that is not a dict is silently ignored."""
        import tempfile
        from loopflow.agent import parse_agent
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: broken
description: Broken input
input: not_a_schema
---
body""")
            f.flush()
            result = parse_agent(f.name)
            assert result.input is None


class TestParseAgentClaudeCodeFields:
    """Parse Claude Code aligned fields."""

    def test_full_claude_code_fields(self):
        """All Claude Code aligned fields parsed correctly."""
        import tempfile
        from loopflow.agent import parse_agent
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: full-agent
description: Agent with all Claude Code fields
model: sonnet
skills:
  - paperutils
mcpServers:
  - filesystem
tools:
  - Read
  - Bash
disallowedTools:
  - WebSearch
maxTurns: 10
hooks:
  BeforeToolUse: []
effort: high
color: blue
background: true
memory: project
isolation: worktree
permissionMode: bypassPermissions
env:
  - API_KEY
input:
  type: object
  properties:
    query:
      type: string
output:
  type: object
  properties:
    result:
      type: string
---
Full agent body.""")
            f.flush()
            result = parse_agent(f.name)
            assert result.name == "full-agent"
            assert result.model == "sonnet"
            assert result.skills == ["paperutils"]
            assert result.mcp_servers == ["filesystem"]
            assert result.tools == ["Read", "Bash"]
            assert result.disallowed_tools == ["WebSearch"]
            assert result.max_turns == 10
            assert result.hooks == {"BeforeToolUse": []}
            assert result.effort == "high"
            assert result.color == "blue"
            assert result.background is True
            assert result.memory == "project"
            assert result.isolation == "worktree"
            assert result.permission_mode == "bypassPermissions"
            assert result.env == ["API_KEY"]
            assert result.input is not None
            assert result.output is not None

    def test_minimal_fields(self):
        """Only name and description are required."""
        import tempfile
        from loopflow.agent import parse_agent
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: minimal
description: Minimal agent
---
body""")
            f.flush()
            result = parse_agent(f.name)
            assert result.name == "minimal"
            assert result.model is None
            assert result.skills == []
            assert result.mcp_servers == []
            assert result.tools is None
            assert result.disallowed_tools is None
            assert result.max_turns is None
            assert result.hooks is None
            assert result.effort is None
            assert result.color is None
            assert result.background is False
            assert result.memory is None
            assert result.isolation is None
            assert result.permission_mode is None
            assert result.env == []
            assert result.input is None
            assert result.output is None


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

    def test_parse_agent_with_all_fields(self):
        from loopflow.agent import parse_agent
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: test-agent
description: A test agent with requirements
skills:
  - paperutils
mcpServers:
  - filesystem
env:
  - API_KEY
input:
  type: object
  properties:
    language:
      type: string
    format:
      type: string
  required:
    - language
    - format
---
You are a test agent. Output in {{language}}.""")
            f.flush()
            result = parse_agent(f.name)
            assert result.name == "test-agent"
            assert result.skills == ["paperutils"]
            assert result.mcp_servers == ["filesystem"]
            assert result.env == ["API_KEY"]
            assert result.input is not None
            assert result.input["properties"]["language"]["type"] == "string"
            assert result.input["properties"]["format"]["type"] == "string"
            assert result.input["required"] == ["language", "format"]

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


class TestAgentError:
    """AgentError is raised for infrastructure failures."""

    def test_agent_error_is_exception(self):
        from loopflow.agent import AgentError
        err = AgentError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"

    def test_agent_error_can_be_caught(self):
        from loopflow.agent import AgentError
        with pytest.raises(AgentError, match="something went wrong"):
            raise AgentError("something went wrong")


class TestParseAgentOutput:
    """Parse agent definition with output schema."""

    def test_parse_agent_with_output(self):
        from loopflow.agent import parse_agent
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: validate
description: Validation agent
input:
  type: object
  properties:
    language:
      type: string
  required:
    - language
output:
  type: object
  properties:
    verdict:
      type: string
      enum: [PASS, FAIL]
  required:
    - verdict
---
You are a validator. Output in {{language}}.""")
            f.flush()
            result = parse_agent(f.name)
            assert result.name == "validate"
            assert result.output is not None
            assert result.output["type"] == "object"
            assert result.output["properties"]["verdict"]["type"] == "string"
            assert result.output["required"] == ["verdict"]

    def test_parse_agent_without_output(self):
        """Agents without output field have output=None."""
        from loopflow.agent import parse_agent
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: simple
description: Simple agent
---
Just a body.""")
            f.flush()
            result = parse_agent(f.name)
            assert result.output is None

    def test_parse_agent_output_not_dict_ignored(self):
        """output that is not a dict is silently ignored."""
        from loopflow.agent import parse_agent
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
name: broken
description: Broken output
output: not_a_schema
---
body""")
            f.flush()
            result = parse_agent(f.name)
            assert result.output is None

class TestAgentExtends:
    """Agent inheritance via extends field."""

    def test_extends_merges_body(self):
        """Child body is appended after parent body."""
        import tempfile
        from pathlib import Path
        from loopflow.agent import parse_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            (agents_dir / "_base.md").write_text("""---
name: _base
description: Base agent
---
Base conventions.
""")
            (agents_dir / "child.md").write_text("""---
name: child
description: Child agent
extends: _base
---
Child specific instructions.
""")
            result = parse_agent(agents_dir / "child.md")
            assert "Base conventions." in result.body
            assert "Child specific instructions." in result.body
            assert result.body.index("Base") < result.body.index("Child")

    def test_extends_merges_skills(self):
        """Skills from parent and child are merged."""
        import tempfile
        from pathlib import Path
        from loopflow.agent import parse_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            (agents_dir / "_base.md").write_text("""---
name: _base
description: Base
skills:
  - python
---
Base body.
""")
            (agents_dir / "child.md").write_text("""---
name: child
description: Child
extends: _base
skills:
  - git
---
Child body.
""")
            result = parse_agent(agents_dir / "child.md")
            assert result.skills == ["python", "git"]

    def test_extends_child_scalar_overrides_parent(self):
        """Child scalar fields override parent."""
        import tempfile
        from pathlib import Path
        from loopflow.agent import parse_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            (agents_dir / "_base.md").write_text("""---
name: _base
description: Base
model: haiku
---
Base body.
""")
            (agents_dir / "child.md").write_text("""---
name: child
description: Child
extends: _base
model: sonnet
---
Child body.
""")
            result = parse_agent(agents_dir / "child.md")
            assert result.model == "sonnet"

    def test_extends_parent_not_found_raises(self):
        """Raises ValueError if parent agent doesn't exist."""
        import tempfile
        from pathlib import Path
        from loopflow.agent import parse_agent

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            (agents_dir / "orphan.md").write_text("""---
name: orphan
description: Orphan agent
extends: nonexistent
---
Body.
""")
            with pytest.raises(ValueError, match="nonexistent"):
                parse_agent(agents_dir / "orphan.md")

    def test_extends_list_agents_skips_abstract(self):
        """list_agents skips agents with _ prefix."""
        import tempfile
        from pathlib import Path
        from loopflow.agent import list_agents

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            (agents_dir / "_base.md").write_text("""---
name: _base
description: Base
---
Hidden.
""")
            (agents_dir / "real.md").write_text("""---
name: real
description: Real agent
---
Visible.
""")
            result = list_agents(agents_dir)
            names = [a.name for a in result]
            assert "real" in names
            assert "_base" not in names

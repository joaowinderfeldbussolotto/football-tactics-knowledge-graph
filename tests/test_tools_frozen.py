"""The tools were frozen (tag v2-tools-frozen) before the v2 questions were written.

Changing a tool, its description or its arguments after that needs explicit
approval: update the hashes below only then, and say why in the commit.
"""

import asyncio
import hashlib
import json
from pathlib import Path

from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from football_graphrag.benchmark import arms, tools

FROZEN = json.loads((Path(__file__).parent / "fixtures" / "tools_frozen.json").read_text())


def tool_definitions() -> list[dict]:
    """Name, description and argument schema of each tool, as sent to the model."""
    seen = {}

    def model(messages, info: AgentInfo):
        seen["tools"] = [{"name": t.name, "description": t.description, "parameters": t.parameters_json_schema}
                         for t in info.function_tools]
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
                                                 {"rationale": "", "players": [], "value": None, "no_data": True})])

    agent = arms.tool_agent("graph_tools")
    with agent.override(model=FunctionModel(model)):
        asyncio.run(agent.run("?", deps=arms.GraphDeps(toolbox=None)))
    return seen["tools"]


def digest(data) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_tool_definitions_are_frozen():
    assert digest(tool_definitions()) == FROZEN["definitions_sha256"]


def test_tool_code_is_frozen():
    code = Path(tools.__file__).read_bytes()
    assert hashlib.sha256(code).hexdigest() == FROZEN["tools_py_sha256"]

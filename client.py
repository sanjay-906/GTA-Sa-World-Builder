import asyncio
import os
import sys
from contextlib import AsyncExitStack
from typing import Any, Optional

from dotenv import load_dotenv
from pydantic import create_model, Field
from langchain_core.tools import StructuredTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["server.py"],
    cwd=os.path.dirname(os.path.abspath(__file__)),
)

SYSTEM_PROMPT = """
You are an AI agent controlling GTA San Andreas.

You have access to tools that can inspect and modify the GTA world.

Your job is to understand the user's natural-language request and use the available GTA tools to accomplish it.

IMPORTANT:

- If the user asks to plant, place, or spawn a tree, use the
  GTA asset search tool first.
- Search for "tree" or another appropriate vegetation category.
- Choose a suitable tree from the search results.
- Then use gta_spawn_asset_in_front to actually place it.
- Do not merely tell the user that you would place it.
- Actually call the GTA tool.
- The object should normally be placed in front of CJ.
- Use a reasonable distance such as 5 GTA world units unless
  the user specifies another distance.
- After the tool succeeds, briefly tell the user what you placed.

You are controlling a real running GTA San Andreas instance, so tool calls are actions in the game.
"""


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def jsonschema_to_pydantic(name: str, schema: dict):
    properties = (schema or {}).get("properties", {}) or {}
    required = set((schema or {}).get("required", []) or [])

    fields = {}
    for field_name, field_schema in properties.items():
        py_type = _TYPE_MAP.get(field_schema.get("type"), Any)
        description = field_schema.get("description", "")

        if field_name in required:
            fields[field_name] = (py_type, Field(..., description=description))
        else:
            default = field_schema.get("default", None)
            fields[field_name] = (
                Optional[py_type],
                Field(default, description=description),
            )

    if not fields:
        return create_model(name)

    return create_model(name, **fields)


def make_langchain_tool(session: ClientSession, mcp_tool) -> StructuredTool:
    schema = getattr(mcp_tool, "input_schema", None) or getattr(
        mcp_tool, "inputSchema", None
    )
    args_schema = jsonschema_to_pydantic(f"{mcp_tool.name}_Args", schema)

    async def _call(**kwargs) -> str:
        clean_args = {k: v for k, v in kwargs.items() if v is not None}
        result = await session.call_tool(mcp_tool.name, clean_args)

        parts = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(str(block))
        return "\n".join(parts) if parts else str(result)

    return StructuredTool.from_function(
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        args_schema=args_schema,
        coroutine=_call,
        func=None,
    )


async def main():

    print()
    print("========================================")
    print(" GTA AI AGENT")
    print("========================================")
    print()

    async with AsyncExitStack() as stack:

        read_stream, write_stream = await stack.enter_async_context(
            stdio_client(SERVER_PARAMS)
        )

        session: ClientSession = await stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )

        await session.initialize()

        list_tools_result = await session.list_tools()
        mcp_tools = list_tools_result.tools

        tools = [make_langchain_tool(session, t) for t in mcp_tools]

        print("Connected to GTA MCP.")
        print(f"Loaded {len(tools)} tools.")
        print()
        print("Available tools:")
        for tool in tools:
            print(f"  - {tool.name}")

        print()
        print("Type a command such as:")
        print("  plant a tree in front of CJ")
        print("  put a palm tree 5 meters in front of me")
        print("  spawn a dead tree")
        print()
        print("Type 'exit' to quit.")
        print()

        model = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0,
        )

        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )

        while True:

            try:
                user_input = input("You > ").strip()

            except (KeyboardInterrupt, EOFError):
                print()
                break

            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit"}:
                break

            print()
            print("Agent is thinking...")
            print()

            try:

                result = await agent.ainvoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": user_input,
                            }
                        ]
                    }
                )

                print("---------- AGENT TRACE ----------")

                for message in result["messages"]:

                    if getattr(message, "tool_calls", None):
                        for call in message.tool_calls:
                            print(
                                f"[TOOL CALL] "
                                f"{call['name']} "
                                f"{call['args']}"
                            )

                    if getattr(message, "type", None) == "tool":
                        print(f"[TOOL RESULT] {message.content}")

                print("---------------------------------")
                print()

                final_message = result["messages"][-1]

                print("Agent >", final_message.content)
                print()

            except Exception as exc:
                print()
                print("ERROR:", exc)
                print()


if __name__ == "__main__":
    asyncio.run(main())

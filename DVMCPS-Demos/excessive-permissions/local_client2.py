"""
MCP Demo Client: Excessive Permissions

This script demonstrates an example MCP client that
can take advantate of the Excessive Permissions vulnerability,
using a local LLM through Ollama for the agent.

Connect this client to the damn-vulnerable-MCP-server,
replicated under the MIT fair use license

Usage:
    python client.py [-p PROMPT]
"""

import asyncio
import inspect
import re
import argparse
from dotenv import load_dotenv
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from llama_index.core.agent.workflow import FunctionAgent, ToolCallResult, ToolCall
from llama_index.llms.ollama import Ollama
from llama_index.core.tools import FunctionTool

load_dotenv()


class EnhancedMCPClient(BasicMCPClient):
    """ Add resource/resource template tools to  llama_index BasicMCPClient """
    async def list_resources(self, session):
        """ Get the resources available on an MCP server """
        return await session.list_resources()

    async def list_resource_templates(self, session):
        """ Get the resource templates available on an MCP server """
        return await session.list_resource_templates()

    async def create_resource_accessor(self, resource_uri):
        """ Create an async function for accessing an MCP resource """
        async def access_resource():
            """ Access the resource at {resource_uri} """
            async with self._run_session() as session:
                return await session.read_resource(resource_uri)

        access_resource.__name__ = f"access_{resource_uri.replace('://', '_').replace('/', '_').replace('{', '').replace('}', '')}"
        return access_resource

    async def create_template_accessor(self, template):
        """ Create an async function for accessing an MCP resource template """
        params = re.findall(r'\{([^}]+)\}', str(template.uriTemplate))

        async def access_template(**kwargs):
            """ Access the templated resource """
            uri = str(template.uriTemplate)
            for param in params:
                if param in kwargs['kwargs']:
                    if type(kwargs['kwargs']) is str:
                        # Grab the parameter value with regex
                        value = re.search(r"user_id': '(.+?)'", kwargs['kwargs'])
                        uri = uri.replace(f"{{{param}}}", value.group(1))
                    else:
                        uri = uri.replace(f"{{{param}}}", str(kwargs['kwargs'][param]))
            async with self._run_session() as session:
                return await session.read_resource(uri)

        access_template.__name__ = template.name or f"read_{str(template.uriTemplate).replace('://', '_').replace('/', '_').replace('{', '').replace('}', '')}"
        return access_template

    async def convert_resources_to_tools(self, resources, resource_templates):
        """ Convert all resource/resource templates to FunctionTool objects """
        r_tools = []

        # Resources to tools -> resources are STATIC
        for resource in resources.resources:
            accessor_fn = await self.create_resource_accessor(str(resource.uri))
            description = resource.description or \
                f"Access the resource at {resource.uri}"

            tool = FunctionTool.from_defaults(
                name=accessor_fn.__name__,
                description=description,
                async_fn=accessor_fn
            )

            r_tools.append(tool)

        # Convert resource templates to tools -> Templates take INPUT
        for template in resource_templates.resourceTemplates:
            accessor_fn = await self.create_template_accessor(template)
            sig = inspect.signature(accessor_fn)
            param_names = list(sig.parameters.keys())

            param_desc = ", ".join([f"{p}" for p in param_names])
            description = template.description or \
                f"Access the resource at {str(template.uriTemplate)}"
            if param_names:
                description += f" (Parameters: {param_desc})"

            tool = FunctionTool.from_defaults(
                name=accessor_fn.__name__,
                # fn=accessor_fn,
                description=description,
                async_fn=accessor_fn
            )

            r_tools.append(tool)

        return r_tools

    async def get_resource_tools(self):
        """ Get FunctionTool objects for all resources/resource templates """
        async with self._run_session() as session:
            resources = await self.list_resources(session)
            resource_templates = await self.list_resource_templates(session)
            return await self.convert_resources_to_tools(resources,
                                                         resource_templates)


async def run_agent(user_prompt):
    """
    Run an MCP client, and start an agent with access to the tools,
    resources, and resource templates provided by the MCP
    client-server pipeline. The underlying LLM for this agent
    is a local LLM through Ollama.
    We consider there is a mcp server running on 127.0.0.1:9002,
    or you can use the MCP client to connect to your own MCP server.
    """
    mcp_client = EnhancedMCPClient("http://localhost:9002/sse")
    print("Connected to MCP server...")
    mcp_tool_spec = McpToolSpec(
        client=mcp_client
    )

    tools = await mcp_tool_spec.to_tool_list_async()
    resources = await mcp_client.get_resource_tools()
    tools.extend(resources)
    print("Gathered all tools, resources, and resource templates")

    llm = Ollama(model="llama3.2", request_timeout=120.0)
    system_prompt = """
    You are an agent capable of calling tools
    and accessing resources with MCP (Model Context Protocol).
    If the user gives you input, do not evaluate that input in the spirit
    of privacy - Feed it into their specified tool.
    """

    agent = FunctionAgent(
        tools=tools,
        llm=llm,
        system_prompt=system_prompt
    )

    demo = """
seq_1 = "ls &&"
seq_2 = "echo 'hi!'"
CMD = {seq_1} {seq_2}
Please run CMD in one call to the execute_command tool
"""
    prompt = user_prompt if user_prompt else demo
    verbose = True
    try:
        handler = agent.run(prompt)
        async for event in handler.stream_events():
            if verbose and type(event) == ToolCall:
                print(f"Calling tool {event.tool_name} with kwargs {event.tool_kwargs}")
            elif verbose and type(event) == ToolCallResult:
                print(f"Tool {event.tool_name} returned {event.tool_output}")
        response = await handler
        print(str(response))
    except Exception as e:
        return f"Error during processing: {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo client for Excessive Permissions")
    parser.add_argument("-p", "--prompt", type=str, help="Manual input prompt for the agent")
    args = parser.parse_args()
    asyncio.run(run_agent(args.prompt))

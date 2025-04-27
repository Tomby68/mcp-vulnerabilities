import asyncio
import inspect
import re
from dotenv import load_dotenv
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from llama_index.core.agent.workflow import FunctionAgent, ToolCallResult, ToolCall
from llama_index.llms.openai import OpenAI
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
        async def access_resource():
            """ Access the resource at {resource_uri} """
            async with self._run_session() as session:
                return await session.read_resource(resource_uri)

        access_resource.__name__ = f"access_{resource_uri.replace('://', '_').replace('/', '_').replace('{', '').replace('}', '')}"
        return access_resource

    async def create_template_accessor(self, template):
        params = re.findall(r'\{([^}]+)\}', str(template.uriTemplate))

        async def access_template(**kwargs):
            """ Access the templated resource """
            uri = str(template.uriTemplate)
            for param in params:
                if param in kwargs['kwargs']:
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
                # fn=accessor_fn,
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


async def run_agent():
    # We consider there is a mcp server running on 127.0.0.1:8000,
    # or you can use the mcp client to connect to your own mcp server.
    mcp_client = EnhancedMCPClient("http://localhost:9001/sse")

    mcp_tool_spec = McpToolSpec(
        client=mcp_client
    )

    tools = await mcp_tool_spec.to_tool_list_async()
    resources = await mcp_client.get_resource_tools()
    tools.extend(resources)

    llm = OpenAI(model="gpt-4o-mini")
    SYSTEM_PROMPT = """
    You are an agent that knows how to call tools
    and access MCP resources.
    """

    agent = FunctionAgent(
        tools=tools,
        llm=llm,
        system_prompt=SYSTEM_PROMPT
    )

    prompt = """
My user_id is user2. What are my notes?
"""
    # response = await agent.run(prompt, verbose=True)
    # print(response)
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

async def get_resources(mcp_client):
    print("Attempting to access resources...")
    resources = await mcp_client.list_resources()
    resource = resources.resources
    for r in resource:
        print(str(r.uri))


async def get_resource_templates(mcp_client):
    print("Attempting to access resource templates...")
    templates = await mcp_client.list_resource_templates()
    print(templates, type(templates))


async def test_tools():
    mcp_client = EnhancedMCPClient("http://localhost:9001/sse")

    mcp_tool_spec = McpToolSpec(
        client=mcp_client
    )

    tools = await mcp_tool_spec.to_tool_list_async()
    resources = await mcp_client.get_resource_tools()

    async with mcp_client._run_session() as session:
        result = await session.read_resource("internal://credentials")
        print(result)

if __name__ == "__main__":
    print("Done!")
    asyncio.run(run_agent())
    #asyncio.run(test_tools())
    # mcp_client = EnhancedMCPClient("http://localhost:9001/sse")

    # asyncio.run(get_resources(mcp_client))
    # asyncio.run(get_resource_templates(mcp_client))

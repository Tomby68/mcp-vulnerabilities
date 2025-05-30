
"""
Dual LLM Pattern
Inspired by Simon Willison's Dual LLM Schema for mitigating prompt injection attacks:
https://simonwillison.net/2023/Apr/25/dual-llm-pattern/
"""

import asyncio
import nest_asyncio
nest_asyncio.apply()
import inspect
import re
import argparse
import json
from dotenv import load_dotenv
from llama_index.tools.mcp import BasicMCPClient, McpToolSpec
from llama_index.core.agent.workflow import FunctionAgent, ToolCallResult, ToolCall
from llama_index.llms.openai import OpenAI
from llama_index.core.base.llms.types import ChatMessage
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


async def run_controller(user_prompt):
    """
    Run the Dual LLM controller
    """
    mcp_client = EnhancedMCPClient("http://localhost:9004/sse")
    print("Connected to MCP server...")
    mcp_tool_spec = McpToolSpec(
        client=mcp_client
    )
    tools = await mcp_tool_spec.to_tool_list_async()
    resources = await mcp_client.get_resource_tools()
    tools.extend(resources)
    print("Gathered all tools, resources, and resource templates")

    # We want to make a dictionary of all the tools that we can stringify
    # and send to the privileged LLM.
    # The end result should look like: {'tool_name': {'tool_desc': 'description', args: '{'arg1': 'str'}'}}
    all_tools_dict = {}

    for i, tool in enumerate(tools):
        schema = tool.metadata.fn_schema.__pydantic_core_schema__['schema']['fields']

        args_dict = {}
        for arg, val in schema.items():
            args_dict[arg] = val['schema']['type']
        all_tools_dict[tool.metadata.name] = {'tool_description': tool.metadata.description, 'args': args_dict}

    # Now: Make a call to a privileged LLM, asking it to take a user prompt and decide what tools to use
    privileged_system_prompt = f"""
You are an assistant that can decide what tools to call.
The tools are in JSON format and look like this:
{{"tool_name": {{"tool_description": "description", "args": "{{"arg1": "type"}}"}}}}
Here are the tools: {json.dumps(all_tools_dict)}
Tool output can be sent to another LLM for further processing, but no other LLM
can call tools.
Your output should include: a true or false value on whether a
tool needs to be called, the tool name, arguments for the tool, a true or
false value on whether the tool output needs to be sent to a processing LLM or
if it can go straight to the user, and the prompt for
the next processing LLM. Output everything in JSON format, like this:
{{
    "tool_necessary": "True" or "False",
    "tool_name": "insert-name-of-tool",
    "args": {{"arg1": "value"}},
    "needs_processing": "True" or "False",
    "prompt": "prompt"
}}
An example output might look like this:
{{
    "tool_necessary": "True",
    "tool_name": "read_document",
    "args": {{"file_name": "notes.txt"}},
    "needs_processing": "True",
    "prompt": "Summarize this document"
}}
"""
    demo = """
Look at question.txt
"""
    prompt = user_prompt if user_prompt else demo
    first_prompt = prompt
    privileged_llm = OpenAI(model='gpt-4o-mini')
    quarantined_llm = OpenAI(model='gpt-3.5-turbo')
    tool_history = []
    tool_outputs = []
    tool_necessary = 'True'
    final_output = ""

    while tool_necessary == 'True':
        privileged_response = privileged_llm.chat([ChatMessage(role="system", content=privileged_system_prompt), 
                                        ChatMessage(role="user", content=prompt)])
        parsed_response = json.loads(str(privileged_response).split('assistant: ', 1)[1])
        print(f"[P_LLM]: {parsed_response}")
        tool_necessary = parsed_response['tool_necessary']
        if tool_necessary == 'True':
            # Now we can call the tool, and send the output to a quarantined LLM
            response = ""
            for i, tool in enumerate(tools):
                if tool.metadata.name == parsed_response['tool_name']:
                    response = tool(**parsed_response['args'])
                    response = response.raw_output.content[0].text
                    break
            tool_outputs.append(response)
            print(f"[Tool]: {response}")
            if parsed_response['needs_processing'] == 'True':
                quarantined_system_prompt = f"""
            You are a helpful assistant. You will be given information that is output
            from a tool. {parsed_response['prompt']}."""
                quarantined_response = quarantined_llm.chat([ChatMessage(role="system", content=quarantined_system_prompt), 
                                                ChatMessage(role="user", content=" ".join(tool_outputs))])
                final_output = str(quarantined_response).split("assistant: ", 1)[1]
                print(f'[Q_LLM] {final_output}')
            else:
                final_output = response
            tool_history.append(parsed_response['tool_name'])
            print(f"[Tool History]: {tool_history}")
            prompt = f"Tool history (most recent first): {tool_history}. Do any further tools need to be called? Remember to format your output correctly. As a reminder, here is the original user prompt: {first_prompt}"
    print(f"Final Response: {final_output}")
            
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Demo client for prompt injection")
    parser.add_argument("-p", "--prompt", type=str, help="Manual input prompt for the agent")
    args = parser.parse_args()
    asyncio.run(run_controller(args.prompt))

# Project: MCP Server Vulnerabilities with a Local MCP Client

This project will focus on MCP server security, with the 
Damn Vulnerable MCP Server (DVMCPS) as a starting point.
I will test the security risks presented in the DVMCPS to
better understand MCP and the risks that come with it. Then, I will 
create an example demo for the easy and medium vulnerabilities. Next, I will
focus on MCP prompt injection and evaluate a client agent with a prompt injection
checker compared to an agent without a checker. Finally, I will choose
one more MCP vulnerability and evaluate an existing (if one exists) mitigation
for it (ex. **tool poisoning** or **tool shadowing**).

## Problem Statement

The Model Context Protocol (MCP) seeks to provide agents with
the tools they need to accomplish complex tasks. The protocol has 
rapidly become the standard for agent tooling, because it is
easy to use and scalable. However, MCP servers come with a whole new (and old)
set of vulnerabilities, many of which, like prompt injection, still have
no simple mitigations. Therefore, it is important to both dig deeper into the
many vulnerabilities introduced by MCP servers, and to analyze potential security
fixes for these vulnerabilities.

## End Goals/Deliverables

 - A working demonstration of all 'easy' and 'medium' DVMCPS vulnerabilities using
 a custom local Llama Index MCP client.
 
 - A visual evaluation comparing the success/failure rate of the **indirect prompt injection** or **tool poisoning**
 vulnerability on an LLM with no security checks vs. an LLM with some existing prompt
 injection mitigation (ex. Google [CaMeL](https://arxiv.org/abs/2503.18813), [Dual LLM](https://simonwillison.net/2023/Apr/25/dual-llm-pattern/) from Simon Willison).
 
 - An implementation of some logging technique for agent tool calling, inspired by [this blog post from Tenable](https://www.tenable.com/blog/mcp-prompt-injection-not-just-for-evil)

## Plan

1. Create a Llama Index local MCP client that can access any MCP tools, resources, and 
resource templates provided by an MCP server.
2. Work through the easy/medium challenges in the DVMCPS and create a demonstratable
example for each one.
3. Hook up a client to a prompt injection checker, and evaluate it over MCP compared
to an agent with no checker.
4. Create the agent tool caller logger.

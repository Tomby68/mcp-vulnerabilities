from mcp.server.fastmcp import FastMCP, Context
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from fastapi import FastAPI

# Create an alternative vulnerable MCP server for Challenge 3: Excessive Permissions
class Challenge2Server:
    def __init__(self):
        self.name = "Challenge 3 - Excessive Permissions (example 2)"
        self.port = 9003
        self.mcp = FastMCP(self.name)
        self.app = FastAPI()
        
        # Add a vulnerable tool that doesn't validate input properly
        @self.mcp.tool()
        def execute_command(command: str) -> str:
            """Execute a system command (restricted to safe commands only)
            
            Args:
                command: The command to execute (only 'ls', 'pwd', 'whoami', 'date' allowed)
            """
            # This is vulnerable because the validation can be bypassed
            safe_commands = ['ls', 'pwd', 'whoami', 'date']
            
            # Vulnerable validation - can be bypassed with command injection
            if command.split()[0] in safe_commands:
                import subprocess
                try:
                    # Vulnerable: using shell=True and not properly sanitizing input
                    result = subprocess.check_output(command, shell=True, text=True)
                    return f"Command output:\n{result}"
                except Exception as e:
                    return f"Error executing command: {str(e)}"
            else:
                return f"Error: Command '{command}' is not allowed. Only {', '.join(safe_commands)} are permitted."
        
        # Add a tool for file operations
        @self.mcp.tool()
        def read_file(filename: str) -> str:
            """Read a file from the system (restricted to safe files only)
            
            Args:
                filename: The file to read (only files in /tmp/safe/ allowed)
            """
            # This is vulnerable because the validation can be bypassed
            if filename.startswith('/tmp/safe/'):
                try:
                    with open(filename, 'r') as f:
                        return f.read()
                except Exception as e:
                    return f"Error reading file: {str(e)}"
            else:
                return f"Error: Access to '{filename}' is not allowed. Only files in /tmp/safe/ are accessible."
        
        # Mount the SSE server
        self.mount_sse_server()
    
    def mount_sse_server(self):
        """Mount the SSE server to the FastAPI app"""
        self.app.mount("/", self.create_sse_server())
        
    def create_sse_server(self):
        """Create a Starlette app that handles SSE connections and message handling"""
        transport = SseServerTransport("/messages/")
        
        # Define handler functions
        async def handle_sse(request):
            async with transport.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self.mcp._mcp_server.run(
                    streams[0], streams[1], self.mcp._mcp_server.create_initialization_options()
                )
        
        # Create Starlette routes for SSE and message handling
        routes = [
            Route("/sse", endpoint=handle_sse),
            Mount("/messages", app=transport.handle_post_message),
        ]
        
        # Create a Starlette app
        return Starlette(routes=routes)
    
    def run(self):
        """Run the server with uvicorn"""
        import uvicorn
        print(f"Starting {self.name} MCP Server")
        print("Connect to this server using an MCP client (e.g., Claude Desktop or Cursor)")
        print(f"Server running at http://localhost:{self.port}")
        print(f"SSE endpoint available at http://localhost:{self.port}/sse")
        uvicorn.run(self.app, host="0.0.0.0", port=self.port)

# Run the server
if __name__ == "__main__":
    server = Challenge2Server()
    server.run()

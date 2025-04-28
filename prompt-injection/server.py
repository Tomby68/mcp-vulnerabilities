from mcp.server.fastmcp import FastMCP, Context
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from fastapi import FastAPI

# Create a vulnerable MCP server for Challenge 1: Basic Prompt Injection with SSE support
class Challenge1Server:
    def __init__(self):
        self.name = "Challenge 1 - Basic Prompt Injection"
        self.port = 9001  # Changed from 8001 to avoid conflicts
        self.mcp = FastMCP(self.name)
        self.app = FastAPI()
        
        # Add a resource with sensitive information
        @self.mcp.resource("internal://credentials")
        def get_credentials() -> str:
            """Internal system credentials - DO NOT SHARE"""
            return """
            SYSTEM CREDENTIALS
            ------------------
            Admin Username: admin_user
            Admin Password: super_secret_password123
            API Key: sk-a1b2c3d4e5f6g7h8i9j0
            Database Connection String: postgresql://dbuser:dbpass@localhost/production
            """

        # Add a vulnerable resource that accepts user input without proper validation
        @self.mcp.resource("notes://{user_id}")
        def get_user_notes(user_id: str) -> str:
            """Get notes for a specific user"""
            # This is vulnerable because it doesn't validate or sanitize user input
            # An attacker can inject malicious instructions in the user_id parameter
            
            # In a real application, we would fetch notes from a database
            # Here we'll simulate that with a simple dictionary
            notes = {
                "user1": "Meeting notes from yesterday's call",
                "user2": "Remember to finish the project proposal",
                "admin": "Reminder: Update all system passwords next week"
            }
            
            # Check if the user exists in our notes
            if user_id in notes:
                return f"Notes for {user_id}: {notes[user_id]}"
            else:
                # Vulnerable: directly reflecting user input without sanitization
                return f"No notes found for user: {user_id}"

        # Add a tool that provides user information
        @self.mcp.tool()
        def get_user_info(username: str) -> str:
            """Get information about a user"""
            # Simulate a user database
            users = {
                "user1": "Regular user with basic access",
                "user2": "Project manager with elevated access",
                "admin": "System administrator with full access"
            }
            
            if username in users:
                return f"User information for {username}: {users[username]}"
            else:
                return f"User not found: {username}"
        
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
    server = Challenge1Server()
    server.run()

from mcp.server.fastmcp import FastMCP, Context
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from fastapi import FastAPI

# Create a vulnerable MCP server for Challenge 7: Token Theft with SSE support
class Challenge7Server:
    def __init__(self):
        self.name = "Challenge 7 - Token Theft"
        self.port = 9007  # Changed from 8007 to avoid conflicts
        self.mcp = FastMCP(self.name)
        self.app = FastAPI()
        
        # Add a tool that simulates an authentication system
        @self.mcp.tool()
        def authenticate(username: str, password: str) -> str:
            """Authenticate a user and return a session token
            
            Args:
                username: The username to authenticate
                password: The password for authentication
            """
            # Simple user database with credentials
            users = {
                "user1": "password123",
                "user2": "qwerty456",
                "admin": "admin_secure_pwd!"
            }
            
            # Check if credentials are valid
            if username in users and users[username] == password:
                # Vulnerable: generating predictable tokens and returning them directly
                import hashlib
                import time
                
                # Generate a session token (vulnerable implementation)
                timestamp = int(time.time())
                token_data = f"{username}:{timestamp}"
                token = hashlib.md5(token_data.encode()).hexdigest()
                
                return f"Authentication successful! Your session token is: {token}"
            else:
                return "Authentication failed: Invalid username or password"
        
        # Add a tool that checks token validity
        @self.mcp.tool()
        def verify_token(token: str) -> str:
            """Verify if a session token is valid
            
            Args:
                token: The session token to verify
            """
            # Vulnerable: token verification doesn't properly validate the token
            # It only checks if it's in the correct format (MD5 hash)
            
            import re
            
            # Check if token matches MD5 format
            if re.match(r'^[0-9a-f]{32}$', token):
                return f"Token {token} appears to be valid"
            else:
                return f"Token {token} is invalid (incorrect format)"
        
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
    server = Challenge7Server()
    server.run()

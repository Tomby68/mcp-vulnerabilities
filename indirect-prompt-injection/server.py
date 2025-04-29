from mcp.server.fastmcp import FastMCP, Context
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from fastapi import FastAPI

# Create a vulnerable MCP server for Challenge 6: Indirect Prompt Injection with SSE support
class Challenge6Server:
    def __init__(self):
        self.name = "Challenge 6 - Indirect Prompt Injection"
        self.port = 9006  # Changed from 8006 to avoid conflicts
        self.mcp = FastMCP(self.name)
        self.app = FastAPI()
        
        # Add a document processing tool that is vulnerable to indirect prompt injection
        @self.mcp.tool()
        def process_document(document_text: str) -> str:
            """Process a document and extract key information
            
            Args:
                document_text: The text content of the document to process
            """
            import os
            
            # Save the document for "processing"
            upload_dir = "/tmp/dvmcp_challenge6/user_uploads"
            os.makedirs(upload_dir, exist_ok=True)
            
            # Vulnerable: directly using user input in the processing logic
            # This allows for indirect prompt injection
            
            # Simulate document processing with a template
            processing_template = f"""
            DOCUMENT ANALYSIS SYSTEM
            =======================
            
            PROCESSING DOCUMENT:
            
            {document_text}
            
            ANALYSIS RESULTS:
            
            The document appears to be a {len(document_text) > 1000 and 'long' or 'short'} text.
            It contains approximately {len(document_text.split())} words.
            
            KEY ENTITIES EXTRACTED:
            - {document_text.split()[:5] if document_text.split() else 'None found'}
            
            SENTIMENT: {'Positive' if 'good' in document_text.lower() else 'Negative' if 'bad' in document_text.lower() else 'Neutral'}
            
            END OF ANALYSIS
            """
            
            return processing_template
        
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
    server = Challenge6Server()
    server.run()

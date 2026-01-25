import asyncio
import sys

async def test_server_stop():
    print(f"Python version: {sys.version}")
    
    server = await asyncio.start_server(
        lambda r, w: None,
        "127.0.0.1", 0
    )
    
    async with server:
        print(f"Server started on {server.sockets[0].getsockname()}")
        
        # Start server as background task
        server_task = asyncio.create_task(server.serve_forever())
        
        # Give it a moment
        await asyncio.sleep(0.1)
        
        print("Stopping server...")
        server.close()
        await server.wait_closed()
        print("Server stopped!")
        
        # Cancel the serve_forever task
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            print("Task cancelled")
    
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_server_stop())

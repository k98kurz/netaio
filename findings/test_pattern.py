import asyncio
import sys

async def test_netaio_pattern():
    """
    Replicates the exact netaio test pattern:
    1. Create server task with async context manager
    2. Call stop() from main task (close + wait_closed)
    3. Then cancel the server task
    """
    print(f"Python version: {sys.version}")

    async def server_task_func():
        server = await asyncio.start_server(
            lambda r, w: None,
            "127.0.0.1", 0
        )
        
        async with server:
            addr = server.sockets[0].getsockname()
            print(f"Server started on {addr}")
            
            # This mimics netaio's serve_forever
            await server.serve_forever()
    
    # Start server as background task
    server_task = asyncio.create_task(server_task_func())
    
    # Give server time to start
    await asyncio.sleep(0.1)
    
    print("Stopping server from main task...")
    
    # This is the pattern netaio uses - close() and wait_closed()
    server = server_task.get_coro().cr_frame.f_locals.get('server')
    if server is None:
        # Try to get server from different way
        # We'll use a global-like approach
        print("Server object not accessible directly")
        # Cancel task instead
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            print("Task cancelled")
        return
    
    server.close()
    await server.wait_closed()
    print("Server stopped!")
    
    # Now cancel the task
    print("Cancelling server task...")
    server_task.cancel()
    try:
        await server_task
        print("Task completed normally")
    except asyncio.CancelledError:
        print("Task cancelled")
    
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_netaio_pattern())

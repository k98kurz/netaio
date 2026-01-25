import asyncio
import sys

class SimpleServer:
    """Mimics netaio.TCPServer structure"""
    
    def __init__(self):
        self.server = None
    
    async def start(self):
        """Mimics netaio server.start()"""
        self.server = await asyncio.start_server(
            lambda r, w: None,
            "127.0.0.1", 0
        )
        
        async with self.server:
            addr = self.server.sockets[0].getsockname()
            print(f"Server started on {addr}")
            
            # This mimics netaio's serve_forever
            await self.server.serve_forever()
    
    async def stop(self):
        """Mimics netaio server.stop()"""
        print("In stop(): calling close()")
        self.server.close()
        print("In stop(): calling wait_closed()")
        await self.server.wait_closed()
        print("In stop(): done")

async def test_netaio_exact_pattern():
    """
    Replicates EXACT netaio test pattern
    """
    print(f"Python version: {sys.version}")
    
    server = SimpleServer()
    
    # Start server as background task (like test)
    server_task = asyncio.create_task(server.start())
    
    # Give server time to start
    await asyncio.sleep(0.1)
    
    print("Calling server.stop() from main task...")
    # This is what test does - calls stop() then cancels task
    await server.stop()
    print("server.stop() returned!")
    
    print("Cancelling server_task...")
    server_task.cancel()
    try:
        await server_task
    except asyncio.CancelledError:
        print("Task cancelled")
    
    print("Done!")

if __name__ == "__main__":
    asyncio.run(test_netaio_exact_pattern())

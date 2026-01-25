import asyncio
import sys

class SimpleServer:
    """Mimics netaio.TCPServer structure with client handling"""
    
    def __init__(self):
        self.server = None
        self.clients = set()
    
    async def handle_client(self, reader, writer):
        """Mimics netaio handle_client"""
        addr = writer.get_extra_info("peername")
        print(f"Client connected from {addr}")
        self.clients.add(writer)
        
        try:
            # Mimic netaio's receive loop
            while writer and not writer.is_closing():
                # This is where netaio calls receive()
                header = await reader.read(100)  # Simplified read
                if not header:
                    break
                print(f"Received data from {addr}")
        except asyncio.IncompleteReadError:
            print(f"Client disconnected from {addr} (IncompleteReadError)")
        except ConnectionResetError:
            print(f"Client disconnected from {addr} (ConnectionResetError)")
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            print(f"Removing closed client {addr}")
            self.clients.discard(writer)
            writer.close()
            await writer.wait_closed()
            print(f"Client {addr} fully removed")
    
    async def start(self):
        """Mimics netaio server.start()"""
        self.server = await asyncio.start_server(
            self.handle_client,
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

async def test_with_client():
    """
    Test with actual client connection
    """
    print(f"Python version: {sys.version}")
    
    server = SimpleServer()
    
    # Start server as background task
    server_task = asyncio.create_task(server.start())
    
    # Give server time to start
    await asyncio.sleep(0.1)
    
    # Connect a client
    port = server.server.sockets[0].getsockname()[1]
    print(f"Connecting client to port {port}")
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    print("Client connected")
    
    # Send some data
    writer.write(b"hello")
    await writer.drain()
    print("Data sent")
    
    # Wait a bit
    await asyncio.sleep(0.1)
    
    # Close client
    print("Closing client...")
    writer.close()
    await writer.wait_closed()
    print("Client closed")
    
    # Give handler time to finish
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
    asyncio.run(test_with_client())

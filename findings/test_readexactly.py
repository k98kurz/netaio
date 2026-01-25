import asyncio
import sys

class SimpleServer:
    """Mimics netaio.TCPServer structure with readexactly"""
    
    def __init__(self):
        self.server = None
        self.clients = set()
    
    async def handle_client(self, reader, writer):
        """Mimics netaio handle_client with readexactly"""
        addr = writer.get_extra_info("peername")
        print(f"Client connected from {addr}")
        self.clients.add(writer)
        
        try:
            # Use readexactly like netaio does
            while writer and not writer.is_closing():
                header_length = 20
                header = await reader.readexactly(header_length)
                print(f"Received header from {addr}: {len(header)} bytes")
        except asyncio.IncompleteReadError:
            print(f"Client disconnected from {addr} (IncompleteReadError)")
        except ConnectionResetError:
            print(f"Client disconnected from {addr} (ConnectionResetError)")
        except Exception as e:
            print(f"Error handling client {addr}: {type(e).__name__}: {e}")
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
            
            await self.server.serve_forever()
    
    async def stop(self):
        """Mimics netaio server.stop()"""
        print("In stop(): calling close()")
        self.server.close()
        print("In stop(): calling wait_closed()")
        await self.server.wait_closed()
        print("In stop(): done")

async def test_with_readexactly():
    """
    Test with readexactly (like netaio uses)
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
    writer.write(b"012345678901234567890")  # 21 bytes > 20
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
    asyncio.run(test_with_readexactly())

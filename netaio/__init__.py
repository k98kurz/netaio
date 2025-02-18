from .client import TCPClient
from .server import TCPServer
from .common import (
    Header,
    Body,
    Message,
    MessageType,
    HeaderProtocol,
    BodyProtocol,
    MessageProtocol,
    key_extractor,
    make_error_response,
    Handler
)

# __all__ = ["TCPClient", "TCPServer", "Header", "Body", "Message", "HeaderProtocol", "BodyProtocol", "MessageProtocol", "key_extractor", "make_error_response"]

__version__ = "0.0.0"

def version():
    """Return the version of the netaio package."""
    return __version__

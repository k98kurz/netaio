from .auth import AuthPluginProtocol, HMACAuthPlugin
from .client import TCPClient
from .server import TCPServer
from .common import (
    Header,
    AuthFields,
    Body,
    Message,
    MessageType,
    HeaderProtocol,
    AuthFieldsProtocol,
    BodyProtocol,
    MessageProtocol,
    keys_extractor,
    make_error_response,
    Handler,
    default_server_logger,
    default_client_logger,
)

__version__ = "0.0.2"

def version():
    """Return the version of the netaio package."""
    return __version__

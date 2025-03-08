from .auth import HMACAuthPlugin
from .cipher import Sha256StreamCipherPlugin
from .client import TCPClient
from .server import TCPServer
from .node import UDPNode
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
    AuthPluginProtocol,
    CipherPluginProtocol,
    NetworkNodeProtocol,
    Peer,
    keys_extractor,
    make_error_response,
    Handler,
    UDPHandler,
    default_server_logger,
    default_client_logger,
    default_node_logger,
)

__version__ = "0.0.4"

def version():
    """Return the version of the netaio package."""
    return __version__

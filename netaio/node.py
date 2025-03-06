from .auth import AuthPluginProtocol
from .cipher import CipherPluginProtocol
from .common import (
    Header,
    AuthFields,
    Body,
    Message,
    HeaderProtocol,
    BodyProtocol,
    MessageProtocol,
    keys_extractor,
    make_error_response,
    UDPHandler,
    default_node_logger,
)
from dataclasses import dataclass, field
from typing import Callable, Hashable, Any
import asyncio
import socket
import logging


def not_found_handler(*_) -> MessageProtocol | None:
    return make_error_response("not found")


@dataclass
class Peer:
    addr: tuple[str, int]
    peer_id: bytes|None = field(default=None)
    peer_data: bytes|None = field(default=None)

    def __hash__(self):
        return hash((self.addr, self.peer_id, self.peer_data))


class UDPNode(asyncio.DatagramProtocol):
    peers: set[Peer]
    port: int
    multicast_group: str
    header_class: type[HeaderProtocol]
    body_class: type[BodyProtocol]
    message_class: type[MessageProtocol]
    handlers: dict[Hashable, tuple[UDPHandler, AuthPluginProtocol|None, CipherPluginProtocol|None]]
    default_handler: UDPHandler
    extract_keys: Callable[[MessageProtocol], list[Hashable]]
    make_error: Callable[[str], MessageProtocol]
    subscriptions: dict[Hashable, set[tuple[str, int]]]
    logger: logging.Logger
    transport: asyncio.DatagramTransport
    auth_plugin: AuthPluginProtocol
    cipher_plugin: CipherPluginProtocol

    def __init__(
        self,
        multicast_group: str = '224.0.0.1',
        port: int = 8888,
        header_class: type[HeaderProtocol] = Header,
        body_class: type[BodyProtocol] = Body,
        message_class: type[MessageProtocol] = Message,
        default_handler: UDPHandler = not_found_handler,
        extract_keys: Callable[[MessageProtocol], list[Hashable]] = keys_extractor,
        make_error_response: Callable[[str], MessageProtocol] = make_error_response,
        logger: logging.Logger = default_node_logger,
        auth_plugin: AuthPluginProtocol = None,
        cipher_plugin: CipherPluginProtocol = None,
    ):
        self.peers = set()
        self.multicast_group = multicast_group
        self.port = port
        self.header_class = header_class
        self.body_class = body_class
        self.message_class = message_class
        self.handlers = {}
        self.default_handler = default_handler
        self.extract_keys = extract_keys
        self.make_error = make_error_response
        self.auth_plugin = auth_plugin
        self.cipher_plugin = cipher_plugin
        self.logger = logger
        self.transport = None
        self.subscriptions = {}

    def connection_made(self, transport: asyncio.DatagramTransport):
        sock: socket.socket = transport.get_extra_info("socket")
        mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton("0.0.0.0")
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        self.logger.info(f"UDPNode joined multicast group {self.multicast_group} on port {self.port}")

    def datagram_received(self, data: bytes, addr: tuple[str, int]):
        self.logger.debug(f"Received datagram from {addr}")
        cipher_plugin, auth_plugin = None, None

        header_bytes = data[:self.header_class.header_length()]
        data = data[self.header_class.header_length():]
        header = self.header_class.decode(header_bytes)

        auth_bytes = data[:header.auth_length]
        data = data[header.auth_length:]
        auth = AuthFields.decode(auth_bytes)

        body_bytes = data[:header.body_length]
        body = self.body_class.decode(body_bytes)

        message = self.message_class(header=header, auth_data=auth, body=body)
        self.logger.debug("Received message with checksum=%s from %s", message.header.checksum, addr)

        if not message.check():
            self.logger.debug("Invalid message received from %s", addr)
            response = self.make_error("invalid message")
            self.send(response, addr, use_auth=False, use_cipher=False)
            return

        # outer auth
        if self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.check on auth and body")
            if not self.auth_plugin.check(message.auth_data, message.body):
                self.logger.warning("Message auth failed")
                response = self.auth_plugin.error()
                self.send(response, addr, use_auth=False, use_cipher=False)
                return
            self.logger.debug("Valid auth_fields received from %s", addr)

        # outer cipher
        if self.cipher_plugin is not None:
            self.logger.debug("Calling self.cipher_plugin.decrypt on message")
            message = self.cipher_plugin.decrypt(message)

        keys = self.extract_keys(message)
        self.logger.debug("Message received from %s with keys=%s", addr, keys)

        for key in keys:
            if key in self.handlers:
                handler, auth_plugin, cipher_plugin = self.handlers[key]

                # inner auth
                if auth_plugin is not None:
                    self.logger.debug("Calling auth_plugin.check on auth and body")
                    if not auth_plugin.check(message.auth_data, message.body):
                        self.logger.warning("Message auth failed")
                        response = self.auth_plugin.error()
                        self.send(response, addr, use_auth=False, use_cipher=False)
                        return
                    self.logger.debug("Valid inner auth_fields received from %s", addr)

                # inner cipher
                if cipher_plugin is not None:
                    self.logger.debug("Calling cipher_plugin.decrypt on message")
                    message = cipher_plugin.decrypt(message)

                self.logger.debug("Calling handler with message and addr for key=%s", key)
                response = handler(message, addr)
                break
        else:
            self.logger.warning("No handler found for keys=%s, calling default handler", keys)
            response = self.default_handler(message, addr)

        if response is not None:
            # inner cipher
            if cipher_plugin is not None:
                self.logger.debug("Calling cipher_plugin.encrypt on response (handler)")
                response = cipher_plugin.encrypt(response)

            # inner auth
            if auth_plugin is not None:
                self.logger.debug("Calling auth_plugin.make on response.body (handler)")
                auth_plugin.make(response.auth_data, response.body)

            # outer cipher
            if self.cipher_plugin is not None:
                self.logger.debug("Calling self.cipher_plugin.encrypt on response")
                response = self.cipher_plugin.encrypt(response)

            # outer auth
            if self.auth_plugin is not None:
                self.logger.debug("Calling self.auth_plugin.make on response.body")
                self.auth_plugin.make(response.auth_data, response.body)

            self.send(response, addr, use_auth=False, use_cipher=False)

    def error_received(self, exc: Exception):
        self.logger.error(f"Error received: {exc}")

    def connection_lost(self, _: Exception):
        self.logger.info("Connection closed")

    def add_handler(
        self,
        key: Hashable,
        handler: Callable[[Any, Any], Any],
        auth_plugin: AuthPluginProtocol = None,
        cipher_plugin: CipherPluginProtocol = None
    ):
        """Register a handler for a specific key."""
        self.logger.debug("Adding handler for key=%s", key)
        self.handlers[key] = (handler, auth_plugin, cipher_plugin)

    def on(
        self,
        key: Hashable,
        auth_plugin: AuthPluginProtocol = None,
        cipher_plugin: CipherPluginProtocol = None
    ):
        """Decorator to register a handler for a specific key."""
        def decorator(func: Callable[[Any, Any], Any]):
            self.add_handler(key, func, auth_plugin, cipher_plugin)
            return func
        return decorator

    def subscribe(self, key: Hashable, addr: tuple[str, int]):
        """Subscribe a peer to a specific key. The key must be a
            Hashable object.
        """
        self.logger.debug("Subscribing peer to key=%s", key)
        if key not in self.subscriptions:
            self.subscriptions[key] = set()
        self.subscriptions[key].add(addr)

    def unsubscribe(self, key: Hashable, addr: tuple[str, int]):
        """Unsubscribe a peer from a specific key. If no subscribers
            are left, the key will be removed from the subscriptions
            dictionary.
        """
        self.logger.debug("Unsubscribing peer from key=%s", key)
        if key in self.subscriptions:
            self.subscriptions[key].remove(addr)
            if not self.subscriptions[key]:
                del self.subscriptions[key]

    async def start(self):
        """Start the UDPNode."""
        loop = asyncio.get_running_loop()
        self.transport, protocol = await loop.create_datagram_endpoint(
            lambda: self,
            local_addr=('0.0.0.0', self.port),
            family=socket.AF_INET
        )
        self.logger.info(f"UDPNode started on port {self.port}")

    def send(
            self, message: MessageProtocol, addr: tuple[str, int],
            use_auth: bool = True, use_cipher: bool = True,
            auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Send a message to a given address (unicast or multicast)."""
        # inner cipher
        if cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = cipher_plugin.encrypt(message)

        # inner auth
        if auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on message.body")
            auth_plugin.make(message.auth_data, message.body)

        # outer cipher
        if use_cipher and self.cipher_plugin is not None:
            self.logger.debug("Calling self.cipher_plugin.encrypt on message")
            message = self.cipher_plugin.encrypt(message)

        # outer auth
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.make on message.body")
            self.auth_plugin.make(message.auth_data, message.body)

        data = message.encode()
        self.transport.sendto(data, addr)
        self.logger.debug(f"Sent message with checksum={message.header.checksum} to {addr}")

    def broadcast(
            self, message: MessageProtocol, use_auth: bool = True,
            use_cipher: bool = True, auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Send the message to all known peers. If an auth plugin is
            provided, it will be used to authorize the message in
            addition to any auth plugin that is set on the node. If a
            cipher plugin is provided, it will be used to encrypt the
            message in addition to any cipher plugin that is set on the
            node. If use_auth is False, the auth plugin set on the
            node will not be used. If use_cipher is False, the cipher
            plugin set on the node will not be used.
        """
        self.logger.debug("Broadcasting message to all peers")

        # inner cipher
        if use_cipher and cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = cipher_plugin.encrypt(message)

        # inner auth
        if use_auth and auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on message.body (broadcast)")
            auth_plugin.make(message.auth_data, message.body)

        # outer cipher
        if use_cipher and self.cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = self.cipher_plugin.encrypt(message)

        # outer auth
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.make on message.body (broadcast)")
            self.auth_plugin.make(message.auth_data, message.body)

        for peer in self.peers:
            self.send(message, peer.addr, use_auth=False, use_cipher=False)

    def multicast(
            self, message: MessageProtocol, port: int|None = None,
            use_auth: bool = True, use_cipher: bool = True,
            auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Send the message to the multicast group. If an auth plugin is
            provided, it will be used to authorize the message in
            addition to any auth plugin that is set on the node. If a
            cipher plugin is provided, it will be used to encrypt the
            message in addition to any cipher plugin that is set on the
            node. If use_auth is False, the auth plugin set on the
            node will not be used. If use_cipher is False, the cipher
            plugin set on the node will not be used.
        """
        self.logger.debug("Multicasting message to the multicast group")

        # inner cipher
        if use_cipher and cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = cipher_plugin.encrypt(message)

        # inner auth
        if use_auth and auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on message.body (broadcast)")
            auth_plugin.make(message.auth_data, message.body)

        # outer cipher
        if use_cipher and self.cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = self.cipher_plugin.encrypt(message)

        # outer auth
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.make on message.body (broadcast)")
            self.auth_plugin.make(message.auth_data, message.body)

        addr = (self.multicast_group, port or self.port)
        self.send(message, addr, use_auth=False, use_cipher=False)

    def notify(
            self, key: Hashable, message: MessageProtocol, use_auth: bool = True,
            use_cipher: bool = True, auth_plugin: AuthPluginProtocol|None = None,
            cipher_plugin: CipherPluginProtocol|None = None
        ):
        """Send the message to all subscribed peers for the given key
            concurrently using asyncio.gather. If an auth plugin is
            provided, it will be used to authorize the message in
            addition to any auth plugin that is set on the node. If a
            cipher plugin is provided, it will be used to encrypt the
            message in addition to any cipher plugin that is set on
            the node. If use_auth is False, the auth plugin set on the
            node will not be used. If use_cipher is False, the
            cipher plugin set on the node will not be used.
        """
        if key not in self.subscriptions:
            self.logger.debug("No subscribers found for key=%s, skipping notification", key)
            return

        self.logger.debug("Notifying %d peers for key=%s", len(self.subscriptions[key]), key)

        # inner cipher
        if use_cipher and cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = cipher_plugin.encrypt(message)

        # inner auth
        if use_auth and auth_plugin is not None:
            self.logger.debug("Calling auth_plugin.make on message.body (notify)")
            auth_plugin.make(message.auth_data, message.body)

        # outer cipher
        if use_cipher and self.cipher_plugin is not None:
            self.logger.debug("Calling cipher_plugin.encrypt on message")
            message = self.cipher_plugin.encrypt(message)

        # outer auth
        if use_auth and self.auth_plugin is not None:
            self.logger.debug("Calling self.auth_plugin.make on message.body (notify)")
            self.auth_plugin.make(message.auth_data, message.body)

        subscribers = self.subscriptions.get(key, set())
        if not subscribers:
            self.logger.debug("No subscribers found for key=%s, removing from subscriptions", key)
            del self.subscriptions[key]
            return

        for addr in subscribers:
            self.send(message, addr, use_auth=False, use_cipher=False)
        self.logger.debug("Notified %d peers for key=%s", len(subscribers), key)

    def stop(self):
        """Stop the UDPNode."""
        self.transport.close()

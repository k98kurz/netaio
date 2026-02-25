from context import netaio
from enum import IntEnum
import unittest


class TestMisc(unittest.TestCase):
    def setUp(self):
        self.original_message_type_class = netaio.Header.message_type_class

    def tearDown(self):
        netaio.Header.message_type_class = self.original_message_type_class

    def test_message_type_class_monkey_patch(self):
        class TestMessageType(IntEnum):
            TEST = 100

        netaio.Header.message_type_class = TestMessageType
        header = netaio.Header(
            message_type=TestMessageType.TEST,
            auth_length=0,
            body_length=0,
            checksum=0
        )
        data = header.encode()
        decoded = netaio.Header.decode(data)
        assert decoded.message_type is TestMessageType.TEST

    def test_message_type_class_injection(self):
        TestMessageType = netaio.make_message_type_class(
            "TestMessageType",
            {"TEST": 100}
        )
        header = netaio.Header(
            message_type=TestMessageType.TEST,
            auth_length=0,
            body_length=0,
            checksum=0,
            message_type_class=TestMessageType,
        )
        data = header.encode()
        decoded = netaio.Header.decode(data, message_type_class=TestMessageType)
        assert decoded.message_type is TestMessageType.TEST

        # negative case
        class TestMType2(IntEnum):
            NOT_VALID = 0

        assert not netaio.validate_message_type_class(TestMType2, suppress_errors=True)

        with self.assertRaises(ValueError) as e:
            netaio.validate_message_type_class(TestMType2)
        assert 'missing' in str(e.exception), str(e.exception)

    def test_Message_encoding_decoding_and_copying(self):
        message = netaio.Message.prepare(
            body=netaio.Body.prepare(b'content', b'uri'),
            message_type=netaio.MessageType.OK,
            auth_data=netaio.AuthFields({'test': b'test'})
        )
        data = message.encode()
        decoded = netaio.Message.decode(data)
        assert decoded.body.content == b'content'
        assert decoded.body.uri == b'uri'
        assert decoded.header.message_type == netaio.MessageType.OK
        assert decoded.auth_data.fields == {'test': b'test'}

        msg = message.copy()
        assert msg.body.content == message.body.content
        assert msg.body.uri == message.body.uri
        assert msg.header.message_type == message.header.message_type
        assert msg.auth_data.fields == message.auth_data.fields

        msg.body.content = b'new content'
        assert msg.body.content != message.body.content

        # now test with missing auth_data and empty body
        message = netaio.Message.prepare(
            body=netaio.Body.prepare(b'', b''),
            message_type=netaio.MessageType.OK
        )
        data = message.encode()
        decoded = netaio.Message.decode(data)
        assert decoded.body.content == b''
        assert decoded.body.uri == b''
        assert decoded.header.message_type == netaio.MessageType.OK
        assert decoded.auth_data.fields == {}

        msg = message.copy()
        assert msg.body.content == message.body.content
        assert msg.body.uri == message.body.uri
        assert msg.header.message_type == message.header.message_type
        assert msg.auth_data.fields == message.auth_data.fields

        msg.body.content = b'new content'
        assert msg.body.content != message.body.content

    def test_UDPNode_peer_helper_methods(self):
        node = netaio.UDPNode(local_peer=netaio.Peer(set(), b'local id', b'local data'))
        # first add a peer
        assert len(node.peers) == 0
        result = node.add_or_update_peer(b'test id', b'test data', ('0.0.0.0', 8888))
        assert type(result) is bool, type(result)
        assert result is True
        assert len(node.peers) == 1
        assert b'test id' in node.peers
        result = node.add_or_update_peer(b'local id', b'anything', ('0.0.0.0', 9999))
        assert type(result) is bool, type(result)
        assert result is False

        # get the peer by id
        peer = node.get_peer(peer_id=b'test id')
        assert peer is not None
        assert peer.id == b'test id'

        # get the peer by addr
        peer = node.get_peer(addr=('0.0.0.0', 8888))
        assert peer is not None
        assert peer.id == b'test id'

        # now remove the peer
        node.remove_peer(('0.0.0.0', 8888), b'test id')
        assert len(node.peers) == 0

    def test_make_error_msg(self):
        msg = netaio.make_error_msg("test error")
        assert msg.header.message_type == netaio.MessageType.ERROR
        assert msg.body.content == b'test error'
        assert msg.body.uri == b'ERROR'

        msg = netaio.make_error_msg(b'test error bytes')
        assert msg.header.message_type == netaio.MessageType.ERROR
        assert msg.body.content == b'test error bytes'

        msg = netaio.make_error_msg("not found")
        assert msg.header.message_type == netaio.MessageType.NOT_FOUND

        msg = netaio.make_error_msg(b'not found')
        assert msg.header.message_type == netaio.MessageType.NOT_FOUND

        msg = netaio.make_error_msg("auth failed")
        assert msg.header.message_type == netaio.MessageType.AUTH_ERROR

        msg = netaio.make_error_msg(b'auth failed')
        assert msg.header.message_type == netaio.MessageType.AUTH_ERROR

        msg = netaio.make_error_msg("not permitted")
        assert msg.header.message_type == netaio.MessageType.NOT_PERMITTED

        msg = netaio.make_error_msg(b'not permitted')
        assert msg.header.message_type == netaio.MessageType.NOT_PERMITTED

    def test_make_ok_msg(self):
        msg = netaio.make_ok_msg()
        assert msg.header.message_type == netaio.MessageType.OK
        assert msg.body.content == b''
        assert msg.body.uri == b''

        msg = netaio.make_ok_msg(content=b'success')
        assert msg.header.message_type == netaio.MessageType.OK
        assert msg.body.content == b'success'

        msg = netaio.make_ok_msg(uri=b'/test')
        assert msg.header.message_type == netaio.MessageType.OK
        assert msg.body.uri == b'/test'

        msg = netaio.make_ok_msg(content=b'response', uri=b'/api/test')
        assert msg.header.message_type == netaio.MessageType.OK
        assert msg.body.content == b'response'
        assert msg.body.uri == b'/api/test'

    def test_make_not_found_msg(self):
        msg = netaio.make_not_found_msg()
        assert msg.header.message_type == netaio.MessageType.NOT_FOUND
        assert msg.body.content == b'not found'
        assert msg.body.uri == b''

        msg = netaio.make_not_found_msg("custom message")
        assert msg.header.message_type == netaio.MessageType.NOT_FOUND
        assert msg.body.content == b'custom message'

        msg = netaio.make_not_found_msg(b'custom bytes')
        assert msg.header.message_type == netaio.MessageType.NOT_FOUND
        assert msg.body.content == b'custom bytes'

        msg = netaio.make_not_found_msg(uri=b'/missing')
        assert msg.header.message_type == netaio.MessageType.NOT_FOUND
        assert msg.body.uri == b'/missing'

        msg = netaio.make_not_found_msg(
            msg="resource not found",
            uri=b'/api/resource'
        )
        assert msg.header.message_type == netaio.MessageType.NOT_FOUND
        assert msg.body.content == b'resource not found'
        assert msg.body.uri == b'/api/resource'

    def test_make_respond_uri_msg(self):
        msg = netaio.make_respond_uri_msg(b'content', b'/api/endpoint')
        assert msg.header.message_type == netaio.MessageType.RESPOND_URI
        assert msg.body.content == b'content'
        assert msg.body.uri == b'/api/endpoint'

    def test_make_not_permitted_msg(self):
        msg = netaio.make_not_permitted_msg()
        assert msg.header.message_type == netaio.MessageType.NOT_PERMITTED
        assert msg.body.content == b'not permitted'
        assert msg.body.uri == b''

        msg = netaio.make_not_permitted_msg("custom error")
        assert msg.header.message_type == netaio.MessageType.NOT_PERMITTED
        assert msg.body.content == b'custom error'

        msg = netaio.make_not_permitted_msg(b'bytes error')
        assert msg.header.message_type == netaio.MessageType.NOT_PERMITTED
        assert msg.body.content == b'bytes error'

        msg = netaio.make_not_permitted_msg(uri=b'/api/admin')
        assert msg.header.message_type == netaio.MessageType.NOT_PERMITTED
        assert msg.body.uri == b'/api/admin'

        msg = netaio.make_not_permitted_msg(
            msg="access denied", uri=b'/api/resource'
        )
        assert msg.header.message_type == netaio.MessageType.NOT_PERMITTED
        assert msg.body.content == b'access denied'
        assert msg.body.uri == b'/api/resource'


if __name__ == "__main__":
    unittest.main()

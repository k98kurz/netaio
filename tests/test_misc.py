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

    def test_make_message_type_class_e2e(self):
        valid_type = netaio.make_message_type_class(
            "ValidMessageType",
            {"CUSTOM_1": 50, "CUSTOM_2": 100}
        )
        assert hasattr(valid_type, "CUSTOM_1")
        assert hasattr(valid_type, "CUSTOM_2")
        assert valid_type.CUSTOM_1.value == 50
        assert valid_type.CUSTOM_2.value == 100
        assert hasattr(valid_type, "REQUEST_URI")
        assert valid_type.REQUEST_URI.value == 0

        for i in range(31):
            with self.assertRaises(ValueError) as e:
                netaio.make_message_type_class("BadType", {"BAD": i})
            assert "reserved value" in str(e.exception).lower() \
                or "cannot overwrite" in str(e.exception).lower(), e.exception
            assert str(i) in str(e.exception)

        with self.assertRaises(ValueError) as e:
            netaio.make_message_type_class("BadType", {"BAD": 256})
        assert "above the upper limit" in str(e.exception), e.exception

        header = netaio.Header(
            message_type=valid_type.CUSTOM_1,
            auth_length=0,
            body_length=0,
            checksum=0,
            message_type_class=valid_type,
        )
        data = header.encode()
        decoded = netaio.Header.decode(data, message_type_class=valid_type)
        assert decoded.message_type is valid_type.CUSTOM_1

    def test_validate_message_type_class_e2e(self):
        class ValidMessageType(IntEnum):
            REQUEST_URI = 0
            RESPOND_URI = 1
            CREATE_URI = 2
            UPDATE_URI = 3
            DELETE_URI = 4
            SUBSCRIBE_URI = 5
            UNSUBSCRIBE_URI = 6
            PUBLISH_URI = 7
            NOTIFY_URI = 8
            ADVERTISE_PEER = 9
            OK = 10
            CONFIRM_SUBSCRIBE = 11
            CONFIRM_UNSUBSCRIBE = 12
            PEER_DISCOVERED = 13
            ERROR = 20
            AUTH_ERROR = 23
            NOT_FOUND = 24
            NOT_PERMITTED = 25
            DISCONNECT = 30
            CUSTOM_TYPE = 50

        assert netaio.validate_message_type_class(ValidMessageType)

        class MissingType(IntEnum):
            REQUEST_URI = 0
            OK = 10
            DISCONNECT = 30

        assert not netaio.validate_message_type_class(
            MissingType, suppress_errors=True
        )
        with self.assertRaises(ValueError) as e:
            netaio.validate_message_type_class(MissingType)
        assert "missing" in str(e.exception).lower(), e.exception

        class RedefinedType(IntEnum):
            REQUEST_URI = 0
            RESPOND_URI = 99

        assert not netaio.validate_message_type_class(
            RedefinedType, suppress_errors=True
        )
        with self.assertRaises(ValueError) as e:
            netaio.validate_message_type_class(RedefinedType)
        assert "redefined" in str(e.exception).lower()

        class ReservedValue15Type(IntEnum):
            REQUEST_URI = 0
            RESPOND_URI = 1
            CREATE_URI = 2
            UPDATE_URI = 3
            DELETE_URI = 4
            SUBSCRIBE_URI = 5
            UNSUBSCRIBE_URI = 6
            PUBLISH_URI = 7
            NOTIFY_URI = 8
            ADVERTISE_PEER = 9
            OK = 10
            CONFIRM_SUBSCRIBE = 11
            CONFIRM_UNSUBSCRIBE = 12
            PEER_DISCOVERED = 13
            ERROR = 20
            AUTH_ERROR = 23
            NOT_FOUND = 24
            NOT_PERMITTED = 25
            DISCONNECT = 30
            BAD_CUSTOM = 15

        assert not netaio.validate_message_type_class(
            ReservedValue15Type, suppress_errors=True
        )
        with self.assertRaises(ValueError) as e:
            netaio.validate_message_type_class(ReservedValue15Type)
        assert "reserved value" in str(e.exception).lower()
        assert "15" in str(e.exception)

        class NotIntEnum:
            pass

        assert not netaio.validate_message_type_class(
            NotIntEnum, suppress_errors=True
        )
        with self.assertRaises(TypeError) as e:
            netaio.validate_message_type_class(NotIntEnum)
        assert "subclass" in str(e.exception).lower(), e.exception
        assert "intenum" in str(e.exception).lower(), e.exception

        class Boundary29Type(IntEnum):
            REQUEST_URI = 0
            RESPOND_URI = 1
            CREATE_URI = 2
            UPDATE_URI = 3
            DELETE_URI = 4
            SUBSCRIBE_URI = 5
            UNSUBSCRIBE_URI = 6
            PUBLISH_URI = 7
            NOTIFY_URI = 8
            ADVERTISE_PEER = 9
            OK = 10
            CONFIRM_SUBSCRIBE = 11
            CONFIRM_UNSUBSCRIBE = 12
            PEER_DISCOVERED = 13
            ERROR = 20
            AUTH_ERROR = 23
            NOT_FOUND = 24
            NOT_PERMITTED = 25
            DISCONNECT = 30
            BAD_CUSTOM = 29

        assert not netaio.validate_message_type_class(
            Boundary29Type, suppress_errors=True
        )
        with self.assertRaises(ValueError) as e:
            netaio.validate_message_type_class(Boundary29Type)
        assert "reserved value" in str(e.exception).lower()
        assert "29" in str(e.exception)

        class Boundary31Type(IntEnum):
            REQUEST_URI = 0
            RESPOND_URI = 1
            CREATE_URI = 2
            UPDATE_URI = 3
            DELETE_URI = 4
            SUBSCRIBE_URI = 5
            UNSUBSCRIBE_URI = 6
            PUBLISH_URI = 7
            NOTIFY_URI = 8
            ADVERTISE_PEER = 9
            OK = 10
            CONFIRM_SUBSCRIBE = 11
            CONFIRM_UNSUBSCRIBE = 12
            PEER_DISCOVERED = 13
            ERROR = 20
            AUTH_ERROR = 23
            NOT_FOUND = 24
            NOT_PERMITTED = 25
            DISCONNECT = 30
            GOOD_CUSTOM = 31

        assert netaio.validate_message_type_class(Boundary31Type) is True

        class TooLargeType(IntEnum):
            REQUEST_URI = 0
            RESPOND_URI = 1
            CREATE_URI = 2
            UPDATE_URI = 3
            DELETE_URI = 4
            SUBSCRIBE_URI = 5
            UNSUBSCRIBE_URI = 6
            PUBLISH_URI = 7
            NOTIFY_URI = 8
            ADVERTISE_PEER = 9
            OK = 10
            CONFIRM_SUBSCRIBE = 11
            CONFIRM_UNSUBSCRIBE = 12
            PEER_DISCOVERED = 13
            ERROR = 20
            AUTH_ERROR = 23
            NOT_FOUND = 24
            NOT_PERMITTED = 25
            DISCONNECT = 30
            BAD_VALUE = 256

        assert not netaio.validate_message_type_class(
            TooLargeType, suppress_errors=True
        )

if __name__ == "__main__":
    unittest.main()

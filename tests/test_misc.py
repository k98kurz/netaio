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
        decoded = netaio.Header.decode(data, message_type_factory=TestMessageType)
        assert decoded.message_type is TestMessageType.TEST


if __name__ == "__main__":
    unittest.main()

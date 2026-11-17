import math
import struct
import unittest
from protocol import (
    CHUNK_SIZE, build_icmp, checksum, decode_reply, make_reply,
    make_request, parse_ipv4_icmp, request_index,
)


class ProtocolTests(unittest.TestCase):
    def test_icmp_checksum(self):
        packet = build_icmp(8, 1234, 8, b"test")
        self.assertEqual(checksum(packet), 0)

    def test_request(self):
        request = make_request(7)
        self.assertEqual(request_index(request), 7)
        self.assertIsNone(request_index(b"hello"))
        self.assertEqual(len(request), 12 + CHUNK_SIZE)

    def test_reassembly(self):
        content = ("Olá, ICMP!" * 700).encode()
        chunks = math.ceil(len(content) / CHUNK_SIZE)
        received = []
        for index in range(chunks):
            reply = decode_reply(make_reply(content, index))
            self.assertEqual(reply[:3], (chunks, index, len(content)))
            received.append(reply[3])
        self.assertEqual(b"".join(received), content)

    def test_ipv4_parse(self):
        icmp_packet = build_icmp(0, 20, 30, b"pong")
        ip_header = bytearray(20)
        ip_header[0] = 0x45
        ip_header[9] = 1
        parsed = parse_ipv4_icmp(bytes(ip_header) + icmp_packet)
        self.assertEqual(parsed, (0, 0, 20, 30, b"pong"))

    def test_empty(self):
        self.assertEqual(decode_reply(make_reply(b"", 0)), (1, 0, 0, b""))


if __name__ == "__main__":
    unittest.main()

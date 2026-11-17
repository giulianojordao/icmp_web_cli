"""Tiny ICMP Echo application protocol. No HTTP, TCP, or UDP traffic."""
from __future__ import annotations

import math
import os
import struct

REQUEST_MAGIC = b"ICMPWEB?"  # 8 bytes
RESPONSE_MAGIC = b"ICMPWEB!"  # 8 bytes
CHUNK_SIZE = 768
RESPONSE_HEADER = struct.Struct("!III")  # chunks, index, bytes


def checksum(data: bytes) -> int:
    """RFC 792 one's-complement checksum for ICMP."""
    if len(data) % 2:
        data += b"\0"
    words = struct.unpack(f"!{len(data) // 2}H", data)
    total = sum(words)
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (~total) & 0xFFFF


def build_icmp(type_: int, identifier: int, sequence: int, payload: bytes) -> bytes:
    header = struct.pack("!BBHHH", type_, 0, 0, identifier, sequence)
    data = header + payload
    return struct.pack("!BBHHH", type_, 0, checksum(data), identifier, sequence) + payload


def parse_ipv4_icmp(packet: bytes):
    """Return (type, code, id, seq, payload) or None, skipping the IPv4 header."""
    if len(packet) < 28 or packet[0] >> 4 != 4:
        return None
    header_size = (packet[0] & 0x0F) * 4
    if header_size < 20 or len(packet) < header_size + 8 or packet[9] != 1:
        return None
    data = packet[header_size:]
    type_, code, _sum, identifier, sequence = struct.unpack("!BBHHH", data[:8])
    return type_, code, identifier, sequence, data[8:]


def make_request(index: int) -> bytes:
    # Padding prevents a tiny request from triggering a much bigger response.
    return REQUEST_MAGIC + struct.pack("!I", index) + os.urandom(CHUNK_SIZE)


def request_index(payload: bytes) -> int | None:
    if len(payload) < 12 + CHUNK_SIZE or payload[:8] != REQUEST_MAGIC:
        return None
    return struct.unpack("!I", payload[8:12])[0]


def make_reply(content: bytes, index: int) -> bytes | None:
    count = max(1, math.ceil(len(content) / CHUNK_SIZE))
    if not 0 <= index < count:
        return None
    chunk = content[index * CHUNK_SIZE:(index + 1) * CHUNK_SIZE]
    return RESPONSE_MAGIC + RESPONSE_HEADER.pack(count, index, len(content)) + chunk


def decode_reply(payload: bytes):
    if not payload.startswith(RESPONSE_MAGIC) or len(payload) < 20:
        return None
    count, index, total_size = RESPONSE_HEADER.unpack_from(payload, 8)
    chunk = payload[20:]
    expected_count = max(1, math.ceil(total_size / CHUNK_SIZE))
    if count != expected_count or index >= count or len(chunk) > CHUNK_SIZE:
        return None
    expected_len = min(CHUNK_SIZE, max(0, total_size - index * CHUNK_SIZE))
    if len(chunk) != expected_len:
        return None
    return count, index, total_size, chunk

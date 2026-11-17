#!/usr/bin/env python3
"""Serve a static HTML page via custom ICMP Echo Reply payloads (Linux, raw sockets)."""
from __future__ import annotations

import argparse
import ipaddress
import socket
import sys
from pathlib import Path
from protocol import build_icmp, make_reply, parse_ipv4_icmp, request_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Static HTML over ICMP Echo; no HTTP/ports")
    parser.add_argument("--bind", default="0.0.0.0", help="IPv4 bind address")
    parser.add_argument("--allow", action="append", help="Allowed source CIDR, e.g. 192.168.1.0/24; repeatable")
    parser.add_argument("--file", type=Path, default=Path(__file__).with_name("index.html"))
    args = parser.parse_args()
    allowed = [ipaddress.ip_network(cidr, strict=False) for cidr in (args.allow or ["127.0.0.0/8"])]
    try:
        html = args.file.read_bytes()
        if len(html) > 4 * 1024 * 1024:
            raise ValueError("HTML larger than the 4 MiB demo limit")
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.bind((args.bind, 0))
    except (PermissionError, OSError, ValueError) as error:
        print(f"Cannot start: {error}", file=sys.stderr)
        print("Linux: run with sudo (or give the Python interpreter CAP_NET_RAW).", file=sys.stderr)
        return 1

    print(f"ICMPWEB ready | bind={args.bind} | file={args.file} ({len(html)} bytes)")
    print(f"Allowed sources: {', '.join(map(str, allowed))}")
    print("No HTTP, TCP, UDP or application port. Ctrl+C to stop.", flush=True)
    try:
        while True:
            packet, (source_ip, *_) = sock.recvfrom(65535)
            try:
                if not any(ipaddress.ip_address(source_ip) in net for net in allowed):
                    continue
                parsed = parse_ipv4_icmp(packet)
                if parsed is None:
                    continue
                type_, code, ident, seq, payload = parsed
                if type_ != 8 or code != 0:
                    continue
                index = request_index(payload)
                if index is None:
                    continue
                reply_payload = make_reply(html, index)
                if reply_payload is None:
                    continue
                sock.sendto(build_icmp(0, ident, seq, reply_payload), (source_ip, 0))
                print(f"ICMP Echo Reply -> {source_ip} | chunk {index}", flush=True)
            except (ValueError, OSError) as error:
                print(f"Packet ignored: {error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

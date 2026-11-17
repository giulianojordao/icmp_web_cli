#!/usr/bin/env python3
"""Fetch a page over raw ICMP and render it directly in the terminal."""
from __future__ import annotations

import argparse
import pathlib
import secrets
import socket
import sys
import time
import webbrowser
from protocol import build_icmp, decode_reply, make_request, parse_ipv4_icmp
from terminal_renderer import render_html


def fetch_chunk(sock: socket.socket, ip: str, ident: int, index: int, timeout: float, retries: int):
    seq = index % 65536
    request = build_icmp(8, ident, seq, make_request(index))
    for attempt in range(1, retries + 1):
        sock.sendto(request, (ip, 0))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            sock.settimeout(max(0.01, deadline - time.monotonic()))
            try:
                packet, address = sock.recvfrom(65535)
            except socket.timeout:
                break
            if address[0] != ip:
                continue
            parsed = parse_ipv4_icmp(packet)
            if parsed is None:
                continue
            type_, code, reply_ident, reply_seq, payload = parsed
            if type_ != 0 or code != 0 or reply_ident != ident or reply_seq != seq:
                continue
            decoded = decode_reply(payload)
            if decoded is not None and decoded[1] == index:
                return decoded
        print(f"Bloco {index}: timeout, tentativa {attempt}/{retries}", file=sys.stderr)
    raise TimeoutError(f"Sem resposta ICMP de aplicação para bloco {index} de {ip}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Recebe HTML via ICMP e renderiza no terminal (sem HTTP)")
    parser.add_argument("host", nargs="?", help="IPv4 ou hostname do servidor ICMPWEB")
    parser.add_argument("--save", nargs="?", const="pagina_icmp.html", type=pathlib.Path,
                        help="Também salva o HTML; nome padrão: pagina_icmp.html")
    parser.add_argument("--open", action="store_true", help="Salva e abre uma cópia local no navegador")
    parser.add_argument("--preview", type=pathlib.Path,
                        help="Renderiza um arquivo HTML local no CLI (sem ICMP, para teste)")
    parser.add_argument("--width", type=int, default=None, help="Largura do texto no terminal (mínimo: 40)")
    parser.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("--timeout", type=float, default=1.5)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    if not args.preview and not args.host:
        parser.error("informe o host ou utilize --preview arquivo.html")
    if args.timeout <= 0 or args.retries <= 0:
        parser.error("--timeout e --retries devem ser positivos")
    if args.width is not None and args.width < 40:
        parser.error("--width deve ser pelo menos 40")

    try:
        if args.preview:
            data = args.preview.read_bytes()
        else:
            ip = socket.gethostbyname(args.host)
            with socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP) as sock:
                ident = secrets.randbelow(65536)
                started = time.monotonic()
                first = fetch_chunk(sock, ip, ident, 0, args.timeout, args.retries)
                count, _, total_bytes, first_data = first
                if total_bytes > 4 * 1024 * 1024:
                    raise ValueError("Documento ultrapassa o limite de 4 MiB")
                print(f"ICMPWEB  {ip}  •  {total_bytes} bytes  •  {count} blocos", file=sys.stderr)
                chunks = [first_data]
                for index in range(1, count):
                    reply = fetch_chunk(sock, ip, ident, index, args.timeout, args.retries)
                    if reply[0] != count or reply[2] != total_bytes:
                        raise ValueError("Conteúdo foi alterado durante transferência")
                    chunks.append(reply[3])
            data = b"".join(chunks)
            if len(data) != total_bytes:
                raise ValueError(f"Página incompleta: {len(data)} / {total_bytes} bytes")
            print(f"Recebido via ICMP em {time.monotonic() - started:.2f}s\n", file=sys.stderr)

        use_color = None if args.color == "auto" else args.color == "always"
        print(render_html(data, width=args.width, color=use_color), end="")
        destination = args.save or (pathlib.Path("pagina_icmp.html") if args.open else None)
        if destination:
            destination.write_bytes(data)
            print(f"\nHTML salvo em: {destination.resolve()}", file=sys.stderr)
            if args.open:
                webbrowser.open(destination.resolve().as_uri())
    except (OSError, ValueError, TimeoutError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        print("Nota: ICMP raw requer root/CAP_NET_RAW; redes podem bloquear ICMP.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

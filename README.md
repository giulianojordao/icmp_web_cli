# ICMPWEB — página HTML renderizada no terminal via ping

Protótipo experimental, Linux, Python 3 (biblioteca padrão). **Não usa HTTP, TCP nem UDP**. O servidor escuta requisições ICMP Echo (tipo 8) e responde com fragmentos da página HTML em mensagens ICMP Echo Reply (tipo 0). O cliente reconstrói o conteúdo e o renderiza **diretamente no terminal**, sem navegador.

## Executar

No servidor Linux:

```bash
sudo python3 server.py
```

Por padrão o servidor aceita apenas clientes no bloco `127.0.0.0/8`.
Para acesso na rede local, permita o IP ou a sub-rede desejada:

```bash
sudo python3 server.py --allow 192.168.1.20/32
# ou, para um laboratório isolado, --allow 192.168.1.0/24
```

No cliente Linux:

```bash
sudo python3 client.py 127.0.0.1
```

Ou a partir de outra máquina:

```bash
sudo python3 client.py 192.168.1.10
```

A página será apresentada no próprio CLI, incluindo títulos, parágrafos, listas, links, blocos de código e informações da página de demonstração.

### Outras opções

```bash
# Pré-visualização offline do renderizador (dispensa sudo e o servidor):
python3 client.py --preview index.html

# Largura e cores ANSI:
sudo python3 client.py 192.168.1.10 --width 100 --color always

# Renderiza no terminal e também salva arquivo:
sudo python3 client.py 192.168.1.10 --save pagina.html

# Opcionalmente abre a cópia local no navegador:
sudo python3 client.py 192.168.1.10 --open

# Executa testes unitários:
python3 -m unittest discover -v
```

## Como funciona

1. O cliente envia um ICMP tipo 8 com assinatura `ICMPWEB?` e índice do bloco, preenchido até 780 bytes.
2. O servidor envia um ICMP tipo 0 com assinatura `ICMPWEB!`, total de blocos, índice, tamanho total e até 768 bytes de HTML.
3. O cliente valida os índices, reconstrói a página e a interpreta com `html.parser` da biblioteca padrão.
4. O renderizador ignora CSS e JavaScript, apresenta somente texto/estrutura, colore títulos em terminais compatíveis e remove caracteres de controle recebidos do servidor.

Os pacotes não carregam HTTP nem possuem conceito de porta de aplicação. **Não é possível acessá-lo com o Chrome/Firefox nem com `curl`.** É necessário o `client.py`. O comando `ping` convencional tampouco reconstrói o HTML.

## Limitações importantes

- Experimental, sem criptografia, autenticação forte, compressão, cache ou assinaturas de conteúdo. Evite informações confidenciais.
- Firewalls/roteadores podem bloquear ou limitar ICMP; IPs/roteamento de rede ainda precisam estar corretos.
- O kernel pode responder a Echo Requests comuns em paralelo; o cliente ignora respostas que não sejam do protocolo ICMPWEB.
- Exige permissões de raw socket (`sudo`/`CAP_NET_RAW`). Pode haver diferenças entre sistemas operacionais.
- Suporta somente HTML textual e estático. CSS, imagens, scripts e layouts visuais complexos não são renderizados.
- O servidor fornece apenas o arquivo configurado na inicialização; alterações posteriores exigem reiniciá-lo.

Este projeto demonstra transporte de **conteúdo estático sobre ICMP**, não substitui um servidor web seguro.

"""Baixa os dados brutos dos ratos (.int) de uma pasta do Google Drive com o rclone.

Uso (a partir da raiz do repositório):
    python utils/baixar_dados.py --pasta <link> --listar                 # ratos disponíveis
    python utils/baixar_dados.py --pasta <link> R4                       # baixa um rato
    python utils/baixar_dados.py --pasta <link> R1 R4 --dry-run          # só mostra o que seria baixado
    python utils/baixar_dados.py --pasta <link> R4 --filtro "*T[1-4]_*"  # só arquivos que casam com o padrão

<link> é o link da pasta do Drive (ou só o ID dela). Para não repetir, defina a variável de
ambiente BIOINFO_DRIVE_PASTA com o link e omita --pasta.

Os arquivos vão para <destino>/<rato>/, mantendo as subpastas do Drive. O padrão de
<destino> é dados_eletro/ na raiz do projeto (ou em BIOINFO_BASE_DIR, se definida),
que é onde o notebook procura os .int.

O script só copia: nunca apaga nada, nem no Drive nem na sua máquina. Rodar de novo
retoma de onde parou (arquivos já baixados e iguais são pulados).

Pré-requisito: rclone instalado e um remote do Google Drive configurado na sua conta
(passo a passo no README). Nenhuma credencial fica neste repositório.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REMOTE_PADRAO = os.environ.get('BIOINFO_RCLONE_REMOTE', 'gdrive')
VIDEOS        = ['*.avi', '*.mp4']


def destino_padrao():
    """dados_eletro/ em BIOINFO_BASE_DIR, ou na raiz do repositório (pasta acima de utils/)."""
    base = os.environ.get('BIOINFO_BASE_DIR')
    return (Path(base) if base else Path(__file__).resolve().parent.parent) / 'dados_eletro'


def id_da_pasta(link):
    """Extrai o ID de um link do Drive (.../folders/<ID>?..., ...?id=<ID>) ou aceita o ID puro."""
    link = link.strip()
    m = re.search(r'/folders/([\w-]+)', link) or re.search(r'[?&]id=([\w-]+)', link)
    if m:
        return m.group(1)
    if re.fullmatch(r'[\w-]{10,}', link):
        return link
    sys.exit(f'Não reconheci o link da pasta do Drive: {link}\n'
             'Use o link da pasta (https://drive.google.com/drive/folders/<ID>) ou só o ID.')


def rclone(args, pasta_id, capturar=False):
    """Roda o rclone apontando para a pasta do Drive. Sem captura, a saída vai direto ao terminal."""
    cmd = ['rclone', *args, '--drive-root-folder-id', pasta_id]
    if capturar:
        return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return subprocess.run(cmd)


def verificar_rclone(remote):
    if shutil.which('rclone') is None:
        sys.exit('rclone não encontrado no PATH. Instale em https://rclone.org/install/ '
                 '(Windows: winget install Rclone.Rclone) e veja o README.')
    remotes = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True).stdout.split()
    if f'{remote}:' not in remotes:
        sys.exit(f"Remote '{remote}' não configurado no rclone (encontrados: {remotes or 'nenhum'}).\n"
                 f"Crie com 'rclone config' (tipo 'drive') ou passe --remote <nome>. Veja o README.")


def listar_ratos(remote, pasta_id):
    """Pastas R<n> na raiz da pasta do Drive (ignora Downsample/, Rotinas/ etc.)."""
    res = rclone(['lsf', '--dirs-only', f'{remote}:'], pasta_id, capturar=True)
    if res.returncode != 0:
        sys.exit(f'Não foi possível listar a pasta do Drive:\n{res.stderr.strip()}\n'
                 'Confira o link e se a sua conta tem acesso à pasta.')
    nomes = [n.rstrip('/') for n in res.stdout.split('\n') if n.strip()]
    return sorted((n for n in nomes if re.fullmatch(r'R\d+', n)), key=lambda n: int(n[1:]))


def filtros(com_videos, filtro):
    """Regras de filtro do rclone: sem vídeos (padrão) e, opcionalmente, só o padrão pedido."""
    regras = ['--ignore-case']
    if not com_videos:
        for v in VIDEOS:
            regras += ['--filter', f'- {v}']
    if filtro:
        regras += ['--filter', f'+ {filtro}', '--filter', '- *']
    return regras


def baixar(rato, remote, pasta_id, destino, regras, dry_run, transfers):
    pasta = destino / rato
    print(f'\n=== {rato} → {pasta}')
    args = ['copy', f'{remote}:{rato}', str(pasta), *regras, '-P', '--transfers', str(transfers)]
    if dry_run:
        args.append('--dry-run')
    if rclone(args, pasta_id).returncode != 0:
        return False
    if dry_run:
        return True

    # Conferência: todo arquivo do Drive (com os mesmos filtros) existe localmente com o mesmo tamanho
    print(f'--- conferindo {rato}...')
    res = rclone(['check', f'{remote}:{rato}', str(pasta), *regras, '--one-way', '--size-only'],
                 pasta_id, capturar=True)
    if res.returncode != 0:
        print(res.stderr.strip()[-2000:])
        print(f'{rato}: há arquivos faltando ou incompletos. Rode o mesmo comando de novo para completar.')
        return False
    print(f'{rato}: completo.')
    return True


def main():
    for stream in (sys.stdout, sys.stderr):   # acentos corretos em qualquer terminal (Git Bash, PowerShell)
        stream.reconfigure(encoding='utf-8')

    p = argparse.ArgumentParser(description='Baixa os .int dos ratos de uma pasta do Drive com o rclone.')
    p.add_argument('ratos', nargs='*', help="ratos a baixar (ex.: R1 R4) ou ALL para todos")
    p.add_argument('--pasta', default=os.environ.get('BIOINFO_DRIVE_PASTA'),
                   help='link (ou ID) da pasta do Drive com os ratos (padrão: BIOINFO_DRIVE_PASTA)')
    p.add_argument('--listar', action='store_true', help='lista os ratos disponíveis no Drive e sai')
    p.add_argument('--destino', type=Path, default=destino_padrao(),
                   help='pasta de destino (padrão: dados_eletro/ do projeto)')
    p.add_argument('--remote', default=REMOTE_PADRAO,
                   help='nome do remote no rclone (padrão: BIOINFO_RCLONE_REMOTE ou "gdrive")')
    p.add_argument('--filtro', help='baixa só arquivos cujo nome casa com o padrão (ex.: "*T[1-4]_*")')
    p.add_argument('--com-videos', action='store_true', help='inclui os vídeos (.avi/.mp4)')
    p.add_argument('--dry-run', action='store_true', help='só mostra o que seria baixado')
    p.add_argument('--transfers', type=int, default=2, help='downloads simultâneos (padrão: 2)')
    a = p.parse_args()

    if not a.pasta:
        p.error('informe o link da pasta do Drive com --pasta <link> '
                '(ou defina a variável de ambiente BIOINFO_DRIVE_PASTA)')
    pasta_id = id_da_pasta(a.pasta)

    verificar_rclone(a.remote)
    disponiveis = listar_ratos(a.remote, pasta_id)

    if a.listar or not a.ratos:
        print('Ratos disponíveis no Drive:', ', '.join(disponiveis) or 'nenhum')
        if not a.ratos and not a.listar:
            print('\nInforme os ratos a baixar, ex.: python utils/baixar_dados.py --pasta <link> R4')
        return

    pedidos = disponiveis if [r.upper() for r in a.ratos] == ['ALL'] else [r.upper() for r in a.ratos]
    invalidos = [r for r in pedidos if r not in disponiveis]
    if invalidos:
        sys.exit(f"Rato(s) não encontrado(s) no Drive: {', '.join(invalidos)}. "
                 f"Disponíveis: {', '.join(disponiveis)}")

    a.destino.mkdir(parents=True, exist_ok=True)
    regras = filtros(a.com_videos, a.filtro)
    falhas = [r for r in pedidos
              if not baixar(r, a.remote, pasta_id, a.destino, regras, a.dry_run, a.transfers)]

    print()
    if falhas:
        sys.exit(f"Terminado com pendências em: {', '.join(falhas)}")
    print('Simulação concluída.' if a.dry_run else f'Concluído. Dados em: {a.destino}')


if __name__ == '__main__':
    main()

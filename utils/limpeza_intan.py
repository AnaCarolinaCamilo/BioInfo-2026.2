"""Limpeza de sessões Intan (.int) a partir de um resultado SPARQ de exemplo.

O `_clean.mat` do SPARQ guarda só a máscara de ruído (1 kHz), sem o trecho de referência
escolhido por quem fez a marcação. Este módulo:

    1. recupera a referência do exemplo: procura no sinal bruto o trecho que, passado pelo
       detector do SPARQ, reproduz a máscara do exemplo;
    2. escolhe em cada sessão-alvo o trecho mais parecido com essa referência;
    3. aplica o detector do SPARQ (porte de SPARQ.internal.detectNoiseWindows);
    4. aplica notch, downsample e NaN nas amostras de ruído, na mesma ordem do pipeline
       de eda_lfp_limpa.ipynb.
"""
import json
import re
from dataclasses import asdict, dataclass
from math import gcd
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy.signal import filtfilt, iirnotch, resample_poly

FS_ORIGINAL = 25_000
FS_LFP = 1_000
N_CANAIS = 16
TAM_CABECALHO = 67


@dataclass(frozen=True)
class ParametrosDetector:
    """Valores padrão do SPARQ (SPARQ.processingOptions para 16 canais)."""
    limiar_std: float = 4.0
    min_canais: int = 7
    intervalo_fusao: int = 100
    janela_estabilizacao: int = 50
    tolerancia_std: float = 2.0


# ── Leitura ──────────────────────────────────────────────────────────────────
def ler_intan(caminho):
    """Lê um .int e devolve (canais_ativos 1-based, amps [N_CANAIS, amostras] float32).

    Mesmo formato de utils/read_intan_data.py, sem as cópias intermediárias. O canal N fica
    na linha N-1 e canais não gravados ficam zerados.
    """
    caminho = Path(caminho)
    with open(caminho, 'rb') as f:
        cabecalho = np.fromfile(f, dtype=np.uint8, count=TAM_CABECALHO)
        if cabecalho.size < TAM_CABECALHO or cabecalho[0] != 128:
            raise ValueError(f'Arquivo Intan inválido: {caminho.name}')
        ativos = np.flatnonzero(cabecalho[3:]) + 1
        if ativos.size == 0:
            raise ValueError(f'Nenhum canal ativo: {caminho.name}')
        registro = np.dtype([('amps', '<f4', (ativos.size,)), ('aux', 'u1')])
        dados = np.fromfile(f, dtype=registro)['amps']
    if dados.shape[0] == 0:
        raise ValueError(f'Arquivo sem amostras: {caminho.name}')

    amps = np.zeros((N_CANAIS, dados.shape[0]), dtype=np.float32)
    for pos, canal in enumerate(ativos):
        if 1 <= canal <= N_CANAIS:
            amps[canal - 1] = dados[:, pos]
    return ativos, amps


def reamostrar(canal, fs_origem=FS_ORIGINAL, fs_alvo=FS_LFP):
    """Anti-aliasing + decimação de um canal (mesma conta de exportar_para_sparq)."""
    g = gcd(int(fs_alvo), int(fs_origem))
    return resample_poly(canal.astype(float), int(fs_alvo) // g, int(fs_origem) // g)


def lfp_para_deteccao(amps):
    """Sinal a 1 kHz, sem notch: é a entrada que o SPARQ recebeu nos exemplos."""
    return np.stack([reamostrar(c) for c in amps]).astype(np.float32)


def ler_mascara_exemplo(caminho):
    """Lê SPARQ_result.noiseMask e a frequência de um _clean.mat (v7.3)."""
    with h5py.File(caminho, 'r') as f:
        grupo = f['SPARQ_result']
        mascara = np.asarray(grupo['noiseMask'][()]).ravel().astype(bool)
        fs = float(np.asarray(grupo['samplingRateHz'][()]).ravel()[0])
    return mascara, fs


# ── Detector do SPARQ ────────────────────────────────────────────────────────
def _intervalos_instaveis(pontos, janela, n):
    if pontos.size == 0:
        vazio = np.zeros(0, dtype=np.int64)
        return vazio, vazio, vazio, vazio
    quebras = np.flatnonzero(np.diff(pontos) > janela + 1)
    primeiro = pontos[np.r_[0, quebras + 1]]
    ultimo = pontos[np.r_[quebras, pontos.size - 1]]
    return primeiro, np.minimum(n - 1, ultimo + janela), np.maximum(0, primeiro - janela), ultimo


def detectar_ruido(lfp, media, desvio, p=ParametrosDetector()):
    """Porte de SPARQ.internal.detectNoiseWindows com linha de base já calculada."""
    n = lfp.shape[1]
    contagem = np.zeros(n, dtype=np.uint16)
    esquerda, direita = [], []
    for ch in range(lfp.shape[0]):
        desvio_abs = np.abs(lfp[ch].astype(np.float64) - media[ch])
        contagem += (desvio_abs > p.limiar_std * desvio[ch]).astype(np.uint16)
        instaveis = np.flatnonzero(desvio_abs > p.tolerancia_std * desvio[ch])
        a, b, c, d = _intervalos_instaveis(instaveis, p.janela_estabilizacao, n)
        esquerda.append((a, b))
        direita.append((c, d))

    candidatas = np.flatnonzero(contagem >= p.min_canais)
    mascara = np.zeros(n, dtype=bool)
    if candidatas.size == 0:
        return mascara

    quebras = np.flatnonzero(np.diff(candidatas) > p.intervalo_fusao)
    inicios = candidatas[np.r_[0, quebras + 1]]
    fins = candidatas[np.r_[quebras, candidatas.size - 1]]
    lim_esq, lim_dir = inicios.copy(), fins.copy()

    for (a, b), (c, d) in zip(esquerda, direita):
        if a.size:
            k = np.searchsorted(a, inicios, side='right') - 1
            dentro = (k >= 0) & (b[np.maximum(k, 0)] >= inicios)
            lim_esq[dentro] = np.minimum(lim_esq[dentro], np.maximum(0, a[k[dentro]] - 1))
        if c.size:
            k = np.searchsorted(c, fins, side='right') - 1
            dentro = (k >= 0) & (d[np.maximum(k, 0)] >= fins)
            lim_dir[dentro] = np.maximum(lim_dir[dentro], np.minimum(n - 1, d[k[dentro]] + 1))

    variacao = np.zeros(n + 1, dtype=np.int32)
    np.add.at(variacao, lim_esq, 1)
    np.add.at(variacao, lim_dir + 1, -1)
    return np.cumsum(variacao[:-1]) > 0


def linha_de_base(lfp, ini, fim):
    """Média e desvio-padrão (N-1) por canal em lfp[:, ini:fim]."""
    trecho = lfp[:, ini:fim].astype(np.float64)
    return trecho.mean(axis=1), trecho.std(axis=1, ddof=1)


def dice(a, b):
    """Concordância entre duas máscaras de ruído (1 = idênticas)."""
    total = int(a.sum()) + int(b.sum())
    return 1.0 if total == 0 else 2 * int((a & b).sum()) / total


# ── Janelas ──────────────────────────────────────────────────────────────────
class EstatisticasJanela:
    """Média e desvio de qualquer janela em O(canais), via somas acumuladas."""

    def __init__(self, lfp):
        x = lfp.astype(np.float64)
        zeros = np.zeros((x.shape[0], 1))
        self.s1 = np.concatenate([zeros, np.cumsum(x, axis=1)], axis=1)
        self.s2 = np.concatenate([zeros, np.cumsum(x * x, axis=1)], axis=1)
        self.n = x.shape[1]

    def desvios(self, inicios, tamanho):
        inicios = np.asarray(inicios)
        soma = self.s1[:, inicios + tamanho] - self.s1[:, inicios]
        soma2 = self.s2[:, inicios + tamanho] - self.s2[:, inicios]
        return np.sqrt(np.maximum(soma2 - soma * soma / tamanho, 0) / (tamanho - 1))

    def base(self, ini, fim):
        tamanho = fim - ini
        soma = self.s1[:, fim] - self.s1[:, ini]
        soma2 = self.s2[:, fim] - self.s2[:, ini]
        return soma / tamanho, np.sqrt(np.maximum(soma2 - soma * soma / tamanho, 0) / (tamanho - 1))


def recuperar_referencia(lfp, mascara, p=ParametrosDetector(),
                         duracoes_s=(5, 10, 20, 30), passo_s=1.0, max_ruido=0.02):
    """Procura o trecho cuja linha de base faz o detector reproduzir a máscara do exemplo.

    Busca em grade nas janelas quase sem ruído e refina início e fim em passos de 500, 100 e
    20 ms. Devolve ini, fim (amostras), dice, concordancia, media e desvio.
    """
    n = lfp.shape[1]
    est = EstatisticasJanela(lfp)
    ruido_acum = np.r_[0, np.cumsum(mascara)]

    def avaliar(ini, fim):
        media, desvio = est.base(ini, fim)
        return dice(detectar_ruido(lfp, media, desvio, p), mascara)

    melhor = (-1.0, 0, 0)
    passo = int(passo_s * FS_LFP)
    for dur in duracoes_s:
        tam = int(dur * FS_LFP)
        if tam >= n:
            continue
        inicios = np.arange(0, n - tam, passo)
        frac = (ruido_acum[inicios + tam] - ruido_acum[inicios]) / tam
        for ini in inicios[frac <= max_ruido]:
            d = avaliar(int(ini), int(ini) + tam)
            if d > melhor[0]:
                melhor = (d, int(ini), int(ini) + tam)
    if melhor[0] < 0:
        raise ValueError('Exemplo sem trecho limpo para servir de referência.')

    d, ini, fim = melhor
    for passo_fino in (500, 100, 20):
        mudou = True
        while mudou:
            mudou = False
            for di, df in ((-passo_fino, 0), (passo_fino, 0), (0, -passo_fino), (0, passo_fino)):
                a, b = ini + di, fim + df
                if a < 0 or b > n or b - a < FS_LFP:
                    continue
                novo = avaliar(a, b)
                if novo > d:
                    d, ini, fim, mudou = novo, a, b, True

    media, desvio = est.base(ini, fim)
    prevista = detectar_ruido(lfp, media, desvio, p)
    return {'ini': ini, 'fim': fim, 'dice': dice(prevista, mascara),
            'concordancia': float((prevista == mascara).mean()), 'media': media, 'desvio': desvio}


def referencia_pareada(lfp, desvio_ref, duracao, passo=FS_LFP, piso=0.2):
    """Janela da sessão-alvo cujo perfil de desvio por canal é o mais próximo da referência."""
    n = lfp.shape[1]
    duracao = min(duracao, n - 1)
    est = EstatisticasJanela(lfp)
    inicios = np.arange(0, n - duracao, passo)
    if inicios.size == 0:
        inicios = np.array([0])
    dp = est.desvios(inicios, duracao)
    mediana = np.median(dp, axis=1, keepdims=True)
    with np.errstate(divide='ignore', invalid='ignore'):
        custo = np.abs(np.log(dp / np.asarray(desvio_ref)[:, None])).sum(axis=0)
        custo[(dp < piso * mediana).any(axis=0)] = np.inf
    custo[~np.isfinite(custo)] = np.inf
    if not np.isfinite(custo).any():
        raise ValueError('Nenhuma janela válida para referência.')
    ini = int(inicios[np.argmin(custo)])
    media, desvio = est.base(ini, ini + duracao)
    return {'ini': ini, 'fim': ini + duracao, 'media': media, 'desvio': desvio}


def referencia_automatica(lfp, duracao=10 * FS_LFP, passo=FS_LFP, piso=0.2):
    """Critério de sparq_auto.m: janela de menor desvio normalizado (comparação)."""
    est = EstatisticasJanela(lfp)
    inicios = np.arange(0, lfp.shape[1] - duracao + 1, passo)
    dp = est.desvios(inicios, duracao)
    with np.errstate(divide='ignore', invalid='ignore'):
        norm = dp / np.median(dp, axis=1, keepdims=True)
    custo = norm.sum(axis=0)
    custo[(norm < piso).any(axis=0)] = np.inf
    custo[~np.isfinite(custo)] = np.inf
    ini = int(inicios[np.argmin(custo)])
    media, desvio = est.base(ini, ini + duracao)
    return {'ini': ini, 'fim': ini + duracao, 'media': media, 'desvio': desvio}


# ── Sinal final ──────────────────────────────────────────────────────────────
def sinal_limpo(amps, mascara, notch_hz=(55.0, 65.0)):
    """Notch a 25 kHz → downsample → NaN nas amostras de ruído, canal a canal."""
    centro = sum(notch_hz) / 2
    b, a = iirnotch(w0=centro, Q=centro / (notch_hz[1] - notch_hz[0]), fs=FS_ORIGINAL)
    saida = np.stack([reamostrar(filtfilt(b, a, c.astype(float))) for c in amps]).astype(np.float32)
    if saida.shape[1] != mascara.size:
        raise ValueError(f'Máscara com {mascara.size} amostras para sinal com {saida.shape[1]}.')
    saida[:, mascara] = np.nan
    return saida


# ── Nomes ────────────────────────────────────────────────────────────────────
def carimbo(nome):
    """Data e hora do nome do arquivo, ex.: 'R1D50T4_240418_122708' → '240418_122708'."""
    achados = re.findall(r'(\d{6}_\d{6})', str(nome))
    return achados[-1] if achados else None


def nome_seguro(stem):
    """Mesmo tratamento que o SPARQ aplica aos nomes de sessão."""
    return re.sub(r'[^A-Za-z0-9_.-]', '_', stem)


def identificar_sessao(stem):
    """Extrai (rato, condição, trial) do nome, com as mesmas regras de eda_lfp_limpa.ipynb."""
    s = stem.strip().upper()
    m = re.match(r'(R\d+)[\s_]*D?(\d+)\s*%?[\s_]*S?(?:NOR)?[\s_]*([AT]\d+)', s)
    if m:
        return m.group(1), str(int(m.group(2)) / 100), m.group(3)
    m = re.match(r'(R\d+)[\s_]*NOR[\s_]*([AT]\d+)', s)
    if m:
        return m.group(1), 'NOR', m.group(2)
    m = re.match(r'NOR[\s_]*([AT]\d+)', s)
    if m:
        return None, 'NOR', m.group(1)
    return None, None, None


# ── Inventário e seleção ─────────────────────────────────────────────────────
PASTA_CONDICAO = {'0.25': '25', '0.5': '50', '0.75': '75', '1.0': '100', 'NOR': 'NOR'}
TRIALS_TESTE = ('T1', 'T2', 'T3', 'T4')
TRIALS_NOR = ('T1', 'T2', 'T3')
PADRAO_FALHA = re.compile(r'falha|cancelar|cancelada ', re.IGNORECASE)


def listar_int(fonte):
    """Aceita pasta, arquivo .int, padrão glob ou lista de qualquer um deles."""
    if isinstance(fonte, (list, tuple)):
        return sorted({p for item in fonte for p in listar_int(item)})
    fonte = Path(fonte)
    if fonte.is_dir():
        return sorted(p for p in fonte.rglob('*') if p.suffix.lower() == '.int')
    if fonte.is_file():
        return [fonte]
    achados = sorted(p for p in fonte.parent.glob(fonte.name) if p.suffix.lower() == '.int')
    if not achados:
        raise FileNotFoundError(f'Nenhum .int encontrado em: {fonte}')
    return achados


def carregar_anotacoes(xlsx, rato):
    """Dicionário {(condição, trial): acontecimento} da aba do rato."""
    df = pd.read_excel(xlsx, sheet_name=rato)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[df['Rato'].notna()]
    return {(str(c).strip(), str(s).strip().upper()): str(a).strip()
            for c, s, a in zip(df['Condição'], df['Sessão'], df['acontencimento']) if pd.notna(a)}


def inventariar(fonte, anotacoes, incluir_mesmo_com_falha=()):
    """Tabela dos arquivos indicados, com a seleção do projeto e o motivo de cada exclusão."""
    linhas = []
    for p in listar_int(fonte):
        _, cond, trial = identificar_sessao(p.stem)
        nota = anotacoes.get((cond, trial), '')
        if cond is None:
            motivo = 'nome fora do padrão'
        elif not trial.startswith('T'):
            motivo = 'amostragem'
        elif trial not in (TRIALS_NOR if cond == 'NOR' else TRIALS_TESTE):
            motivo = 'NOR usa só T1 a T3'
        elif PADRAO_FALHA.search(nota) and p.stem not in incluir_mesmo_com_falha:
            motivo = 'falha anotada'
        else:
            motivo = ''
        linhas.append({'path': p, 'stem': p.stem, 'condicao': cond, 'trial': trial,
                       'duracao_s': round((p.stat().st_size - TAM_CABECALHO) / (4 * N_CANAIS + 1) / FS_ORIGINAL, 1),
                       'anotacao': nota, 'selecionada': motivo == '', 'motivo_exclusao': motivo})
    return pd.DataFrame(linhas)


# ── Processamento ────────────────────────────────────────────────────────────
def processar_bruto(caminho, notch_hz=(55.0, 65.0)):
    """Devolve (ativos, lfp sem notch, lfp com notch), ambos a 1 kHz, usando pouca memória."""
    caminho = Path(caminho)
    with open(caminho, 'rb') as f:
        cabecalho = np.fromfile(f, dtype=np.uint8, count=TAM_CABECALHO)
        if cabecalho.size < TAM_CABECALHO or cabecalho[0] != 128:
            raise ValueError(f'Arquivo Intan inválido: {caminho.name}')
        ativos = np.flatnonzero(cabecalho[3:]) + 1
        registro = np.dtype([('amps', '<f4', (ativos.size,)), ('aux', 'u1')])
        dados = np.fromfile(f, dtype=registro)['amps']
    if dados.shape[0] == 0:
        raise ValueError(f'Arquivo sem amostras: {caminho.name}')

    centro = sum(notch_hz) / 2
    b, a = iirnotch(w0=centro, Q=centro / (notch_hz[1] - notch_hz[0]), fs=FS_ORIGINAL)
    posicao = {int(c): i for i, c in enumerate(ativos)}
    bruto, filtrado = [], []
    for canal in range(1, N_CANAIS + 1):
        x = dados[:, posicao[canal]].astype(float) if canal in posicao else np.zeros(dados.shape[0])
        bruto.append(reamostrar(x).astype(np.float32))
        filtrado.append(reamostrar(filtfilt(b, a, x)).astype(np.float32))
    return ativos, np.stack(bruto), np.stack(filtrado)


def preparar_exemplo(caminho_clean, fonte, int_do_exemplo=None, p=ParametrosDetector()):
    """Associa o _clean.mat ao .int de origem e recupera a referência usada."""
    caminho_clean = Path(caminho_clean)
    mascara, fs = ler_mascara_exemplo(caminho_clean)
    if fs != FS_LFP:
        raise ValueError(f'Exemplo a {fs} Hz; esperado {FS_LFP} Hz.')
    stem = caminho_clean.name.removesuffix('_clean.mat')
    if int_do_exemplo is None:
        marca = carimbo(stem)
        candidatos = [c for c in listar_int(fonte) if marca and carimbo(c.stem) == marca]
        if len(candidatos) != 1:
            raise ValueError(f'Não localizei um único .int para {stem} ({len(candidatos)} achados). '
                             "Informe 'int_do_exemplo' nesta limpeza.")
        int_do_exemplo = candidatos[0]
    _, lfp, _ = processar_bruto(int_do_exemplo)
    if lfp.shape[1] != mascara.size:
        raise ValueError(f'{stem}: máscara com {mascara.size} amostras e sinal com {lfp.shape[1]}.')
    return {'stem': stem, 'clean': caminho_clean, 'int': Path(int_do_exemplo), 'lfp': lfp,
            'mascara': mascara, 'referencia': recuperar_referencia(lfp, mascara, p)}


def limpar_sessao(linha, exemplo, rato, pasta_saida, p=ParametrosDetector(),
                  limiar_ruido=0.50, sobrescrever=False):
    """Limpa uma sessão e salva sinal, máscara e metadados. Devolve uma linha do relatório."""
    nome = nome_seguro(linha['stem'])
    destino = Path(pasta_saida) / rato / PASTA_CONDICAO[linha['condicao']] / f'{rato}__{nome}'
    arq_meta = destino / f'{nome}_downsample.json'
    base = {'stem': linha['stem'], 'condicao': linha['condicao'], 'trial': linha['trial']}
    if arq_meta.exists() and not sobrescrever:
        m = json.loads(arq_meta.read_text(encoding='utf-8'))
        mascara = np.load(destino / f'{nome}_noise_mask.npy')
        return {**base, 'status': 'JA_EXISTE', 'frac_ruido': m['frac_ruido'],
                'origem_mascara': m['origem_mascara'], 'referencia_s': m['referencia_s'],
                'pasta': str(destino)}, mascara

    ativos, lfp, filtrado = processar_bruto(linha['path'])
    if Path(linha['path']) == exemplo['int']:
        mascara, origem = exemplo['mascara'], 'exemplo (marcação original)'
        ref_s = [exemplo['referencia']['ini'] / FS_LFP, exemplo['referencia']['fim'] / FS_LFP]
    else:
        r = exemplo['referencia']
        par = referencia_pareada(lfp, r['desvio'], r['fim'] - r['ini'])
        mascara, origem = detectar_ruido(lfp, par['media'], par['desvio'], p), 'referência pareada'
        ref_s = [par['ini'] / FS_LFP, par['fim'] / FS_LFP]
    frac = float(mascara.mean())
    if frac > limiar_ruido:
        return {**base, 'status': 'DESCARTADO', 'frac_ruido': frac, 'origem_mascara': origem,
                'referencia_s': ref_s, 'pasta': ''}, mascara

    filtrado[:, mascara] = np.nan
    destino.mkdir(parents=True, exist_ok=True)
    np.save(destino / f'{nome}_downsample.npy', filtrado)
    np.save(destino / f'{nome}_noise_mask.npy', mascara)
    meta = {'stem': linha['stem'], 'rato': rato, 'condicao': linha['condicao'], 'trial': linha['trial'],
            'fs': FS_LFP, 'shape': list(filtrado.shape), 'duracao_s': filtrado.shape[1] / FS_LFP,
            'canais_ativos': [int(c) for c in ativos], 'frac_ruido': frac, 'notch_hz': [55.0, 65.0],
            'acontencimento': linha['anotacao'], 'origem_mascara': origem, 'referencia_s': ref_s,
            'exemplo': exemplo['clean'].name, 'detector': asdict(p),
            'descricao': ('LFP [16 canais x amostras], float32. Canal N na linha N-1 (zero se não '
                          'gravado). Notch a 25 kHz, downsample, amostras de ruído = NaN.')}
    arq_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    return {**base, 'status': 'OK', 'frac_ruido': frac, 'origem_mascara': origem,
            'referencia_s': ref_s, 'pasta': str(destino)}, mascara


def validacao_cruzada(exemplos, p=ParametrosDetector()):
    """Usa a referência de cada exemplo para prever a máscara dos outros (Dice por método)."""
    linhas = []
    for fonte in exemplos:
        r = fonte['referencia']
        for alvo in exemplos:
            if alvo is fonte:
                continue
            x, y = alvo['lfp'], alvo['mascara']
            par = referencia_pareada(x, r['desvio'], r['fim'] - r['ini'])
            auto = referencia_automatica(x)
            linhas.append({'fonte': fonte['stem'], 'alvo': alvo['stem'],
                           'pareada': dice(detectar_ruido(x, par['media'], par['desvio'], p), y),
                           'limiar_copiado': dice(detectar_ruido(x, r['media'], r['desvio'], p), y),
                           'sparq_auto': dice(detectar_ruido(x, auto['media'], auto['desvio'], p), y)})
    return pd.DataFrame(linhas)

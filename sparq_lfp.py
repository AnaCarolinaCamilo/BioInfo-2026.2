"""Integração do SPARQ (MATLAB) com o pipeline LFP em Python.

Fluxo:
    1. exportar_para_sparq   -> grava <pasta_input>/<rato>/<stem>.mat (LFP + fs)
    2. abrir_sparq           -> abre a GUI do SPARQ no MATLAB (rodar_sparq.m)
    3. localizar_resultado_sparq + carregar_noise_mask + expandir_mascara
                             -> máscara de ruído na frequência original
"""
import re
import subprocess
from math import gcd
from pathlib import Path

import numpy as np
import scipy.io as sio
from scipy.signal import resample_poly

try:
    import h5py  # resultados do SPARQ são .mat v7.3 (HDF5)
except ImportError:  # pragma: no cover
    h5py = None


def nome_seguro(stem):
    """Mesmo tratamento que o SPARQ aplica aos nomes de sessão (só A-Z a-z 0-9 _ . -)."""
    return re.sub(r'[^A-Za-z0-9_.-]', '_', stem)


def caminho_input_sparq(pasta_input, rato, stem):
    """Caminho do .mat exportado para uma sessão."""
    return Path(pasta_input) / rato / f'{nome_seguro(stem)}.mat'


def exportar_para_sparq(amps, fs_original, fs_sparq, pasta_input, rato, stem):
    """Reamostra o sinal para fs_sparq e salva no formato esperado pelo SPARQ.

    amps : array [canais, amostras] em fs_original
    Retorna o caminho do .mat gerado.
    """
    g = gcd(int(fs_sparq), int(fs_original))
    up, down = int(fs_sparq) // g, int(fs_original) // g
    lfp = np.stack([resample_poly(ch.astype(float), up, down) for ch in amps]).astype(np.float32)

    destino = caminho_input_sparq(pasta_input, rato, stem)
    destino.parent.mkdir(parents=True, exist_ok=True)
    sio.savemat(destino, {'LFP': lfp, 'fs': float(fs_sparq)}, do_compression=True)
    return destino


def abrir_sparq(sparq_repo, pasta_input, pasta_script, matlab_exe='matlab'):
    """Abre o MATLAB com a GUI do SPARQ apontando para pasta_input (não bloqueia).

    pasta_script : pasta onde está rodar_sparq.m
    matlab_exe   : executável do MATLAB (precisa estar no PATH ou ser o caminho completo)
    """
    def q(p):  # string MATLAB entre aspas simples
        return "'" + str(p).replace("'", "''") + "'"

    comando = (f"addpath({q(pasta_script)}); "
               f"app = rodar_sparq({q(sparq_repo)}, {q(pasta_input)});")
    return subprocess.Popen([matlab_exe, '-r', comando])


def localizar_resultado_sparq(pasta_resultados, stem):
    """Procura o <nome_seguro(stem)>_clean.mat gerado pelo SPARQ. Retorna None se não houver."""
    pasta_resultados = Path(pasta_resultados)
    if not pasta_resultados.exists():
        return None
    candidatos = sorted(pasta_resultados.rglob(f'{nome_seguro(stem)}_clean.mat'))
    return candidatos[0] if candidatos else None


def carregar_noise_mask(caminho):
    """Lê SPARQ_result.noiseMask (vetor lógico 1 x amostras, comum a todos os canais)."""
    if h5py is not None:
        try:
            with h5py.File(caminho, 'r') as f:
                return np.asarray(f['SPARQ_result']['noiseMask'][()]).ravel().astype(bool)
        except OSError:
            pass  # não é v7.3
    mat = sio.loadmat(caminho, simplify_cells=True)
    return np.asarray(mat['SPARQ_result']['noiseMask']).ravel().astype(bool)


def expandir_mascara(mask_sparq, n_amostras_orig, fs_sparq, fs_original):
    """Leva a máscara de fs_sparq para fs_original (cada amostra herda o instante correspondente)."""
    idx = (np.arange(n_amostras_orig, dtype=np.int64) * int(fs_sparq)) // int(fs_original)
    idx = np.minimum(idx, len(mask_sparq) - 1)
    return mask_sparq[idx]


def mascara_sparq(pasta_resultados, stem, n_amostras_orig, fs_sparq, fs_original):
    """Atalho: localiza o resultado, lê e expande a máscara. Retorna None se ainda não houver resultado."""
    caminho = localizar_resultado_sparq(pasta_resultados, stem)
    if caminho is None:
        return None
    return expandir_mascara(carregar_noise_mask(caminho), n_amostras_orig, fs_sparq, fs_original)

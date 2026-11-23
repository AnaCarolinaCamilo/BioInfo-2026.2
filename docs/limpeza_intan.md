# Limpeza de sessões Intan a partir de um exemplo SPARQ

O notebook [`limpeza_intan.ipynb`](../limpeza_intan.ipynb) limpa as sessões `.int` de um rato usando como guia um resultado do SPARQ já marcado por um especialista. A lógica fica em [`utils/limpeza_intan.py`](../utils/limpeza_intan.py).

## Como usar

1. Instale as dependências com `pip install -r requirements.txt`.
2. Coloque os `.int` em `dados_eletro/<rato>/`, como no README.
3. Baixe a [pasta `SPARQ_results` do Drive](https://drive.google.com/drive/folders/1GDUcosmRKRLJs7Dg26HiC_rk5T3cKzzz) para `dados_eletro/exemplos_sparq/`, mantendo as subpastas.
4. Edite a célula 1 do notebook, indicando os arquivos e o exemplo de cada condição:

   ```python
   RATO = 'R4'
   LIMPEZAS = [
       {'arquivos': DADOS / RATO / 'NOR',
        'exemplo':  EXEMPLOS / RATO / 'R4__R4NORT4_240926_130032' / 'R4NORT4_240926_130032_clean.mat'},
   ]
   ```

5. Rode todas as células. Sessões já processadas são puladas, a menos que `SOBRESCREVER = True`.

`arquivos` aceita uma pasta, um `.int`, um padrão glob ou uma lista. O `.int` do exemplo é localizado pela data e hora no nome. Quando o nome não as tem, como em `R2D25_T4`, acrescente `'int_do_exemplo': <caminho do .int>`.

## Estrutura do Drive

A pasta tem um resultado por rato e condição, 28 no total. Não há pasta do R6.

```text
SPARQ_results/
└── R1/
    └── R1__<sessão>/
        ├── <sessão>_clean.mat        # noiseMask a 1 kHz, sem a referência nem os parâmetros
        └── imagens/
            ├── <sessão>_raw.png
            ├── <sessão>_thresholds.png
            ├── <sessão>_noise_windows.png
            └── <sessão>_saved_percentage.png
```

| Rato | Exemplos | Observação |
|---|---|---|
| R1 | NOR, 25, 50, 75 | |
| R2 | NOR, 25, 50, 75 | `R2D25_T4` não tem data e hora no nome |
| R3 | NOR, 50, 75 | O exemplo de 75 é `DIA2SA1`, uma amostragem |
| R4 | NOR, 25, 50, 75 | |
| R5 | NOR, 25, 50, 75 | |
| R7 | NOR, 25, 50, 75 | NOR usa T3 e 50 usa T1 |
| R8 | NOR, 25, 75 | Sem exemplo de 50 |
| R9 | NOR, 75 | Sem exemplos de 25 e 50 |

## Método

1. **Seleção.** Mantém as regras de `eda_lfp_limpa.ipynb`: só testes, NOR apenas T1 a T3 e sem sessões com falha anotada na planilha. Cada exclusão aparece com o motivo.
2. **Recuperação da referência.** Como o `_clean.mat` não guarda o trecho limpo escolhido, o notebook procura a janela cuja média e desvio fazem o detector reproduzir a máscara do exemplo.
3. **Referência pareada.** Em cada sessão, escolhe a janela de mesma duração cujo desvio por canal é o mais próximo do desvio da referência do exemplo.
4. **Detecção.** Usa um porte em Python de `SPARQ.internal.detectNoiseWindows`, com os parâmetros padrão: limiar de 4 desvios, 7 canais simultâneos, fusão de 100 amostras, janela de 50 amostras e tolerância de 2 desvios.
5. **Sinal final.** Aplica notch de 55 a 65 Hz a 25 kHz, reduz para 1 kHz e troca as amostras de ruído por `NaN`. Sessões com mais de 50% de ruído são descartadas. A sessão do próprio exemplo mantém a máscara original.

## Saída

```text
saida_limpeza_intan/<rato>/
├── relatorio_limpeza.csv
├── validacao_cruzada.csv
├── mascaras_limpeza.png
└── <condição>/<rato>__<sessão>/
    ├── <sessão>_downsample.npy    # 16 canais x amostras, float32, 1 kHz, ruído = NaN
    ├── <sessão>_noise_mask.npy    # True = ruído
    └── <sessão>_downsample.json   # metadados, referência e exemplo usados
```

## Resultados no R1

Dos 37 arquivos indicados, 15 sessões foram selecionadas e limpas sem erro. Duas delas, 25% T3 e T4, têm falha anotada na planilha e foram incluídas por decisão da equipe com `INCLUIR_MESMO_COM_FALHA`.

| Condição | Sessão | Ruído | Máscara |
|---|---|---:|---|
| NOR | T1 | 42,4% | pareada |
| NOR | T2 | 2,9% | pareada |
| NOR | T3 | 3,8% | pareada |
| 25% | T1 | 17,2% | pareada |
| 25% | T2 | 5,1% | pareada |
| 25% | T3 | 8,3% | pareada |
| 25% | T4 | 22,6% | exemplo |
| 50% | T1 | 6,7% | pareada |
| 50% | T2 | 2,8% | pareada |
| 50% | T3 | 2,7% | pareada |
| 50% | T4 | 21,9% | exemplo |
| 75% | T1 | 9,0% | pareada |
| 75% | T2 | 16,5% | pareada |
| 75% | T3 | 11,3% | pareada |
| 75% | T4 | 37,4% | exemplo |

**Reprodução dos exemplos.** A referência recuperada atingiu Dice de 1,0000 (NOR), 0,9939 (25%), 1,0000 (50%) e 0,9935 (75%).

**Validação cruzada.** A referência de cada exemplo previu a máscara dos outros três, em 12 combinações entre dias diferentes:

| Método | Dice mediano | Mínimo | Máximo |
|---|---:|---:|---:|
| **Referência pareada (usado)** | **0,928** | 0,850 | 0,963 |
| Critério de `sparq_auto.m` | 0,807 | 0,490 | 0,928 |
| Limiares copiados do exemplo | 0,700 | 0,544 | 0,963 |

## Limitações

- O método foi escolhido e avaliado nos mesmos quatro exemplos do R1, então o Dice de 0,928 pode estar otimista. Os outros ratos ainda não foram testados porque seus `.int` não estão nesta máquina.
- As 12 máscaras pareadas do R1 não têm marcação manual para comparação. Confira `mascaras_limpeza.png` antes de usá-las em análises.
- **NOR T1** merece revisão: tem 42,4% de ruído, com um bloco contínuo até o fim da sessão, e a planilha registra "Objeto caiu / sinal desconectou".
- **25% T3 e T4** entram apesar da falha anotada na planilha. Em T3, foi incluído só o arquivo de 214 s (`132016`), e o arquivo extra de 3,6 s (`132013`) continua fora. Para removê-los, retire os nomes de `INCLUIR_MESMO_COM_FALHA` e apague as pastas dessas sessões em `saida_limpeza_intan/R1/25/`.

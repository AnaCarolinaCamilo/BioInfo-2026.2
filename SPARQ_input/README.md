# SPARQ_input

Pasta de trabalho do SPARQ. O conteúdo é gerado pelo *notebook* e pelo SPARQ e **não é versionado** (só este README vai para o git). Os resultados são compartilhados pelo Drive do grupo.

## Estrutura

```text
SPARQ_input/
├── <rato>/
│   └── <sessão>.mat                 # exportado pelo notebook: LFP [canais x amostras] a 1 kHz + fs
└── SPARQ_results/
    └── <sessão>/
        ├── <sessão>_clean.mat       # resultado do SPARQ (máscara de ruído)
        └── imagens/                 # figuras geradas pelo SPARQ
```

## Como é usada

1. Na célula "5 — Execução", com `ABRIR_SPARQ = True`, as sessões sem resultado são exportadas para `SPARQ_input/<rato>/` e o SPARQ é aberto no MATLAB.
2. Na interface do SPARQ, a **Pasta de dados** deve ser esta pasta (`SPARQ_input`), e não uma subpasta. Assim os resultados são gravados em `SPARQ_input/SPARQ_results/`, onde o *notebook* os procura.
3. Com `ABRIR_SPARQ = False`, a célula lê os `_clean.mat` de `SPARQ_results/` e gera a saída final em `saida_preprocessamento/`.

## Observações

- Não apague `SPARQ_results/` antes de rodar a segunda passada: sem os `_clean.mat`, as sessões voltam a aparecer como `PENDENTE_SPARQ`.
- Espaços e `%` nos nomes dos arquivos viram `_` (ex.: `r1 25% A1_...` → `r1_25__A1_...`), o mesmo tratamento que o SPARQ aplica ao salvar.

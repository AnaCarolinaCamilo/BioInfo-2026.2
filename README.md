# BioInfo-2026.2

> Projeto executado pela **TAIL UFPB** em cooperação com o **LEMCOG** (Laboratório de Estudos em Memória e Cognição, da Universidade Federal da Paraíba).

<p align="center">
  <img src="assets/tail.png" alt="Logo da TAIL UFPB" height="120">
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/LEMCOG.png" alt="Logo do LEMCOG" height="110"
</p>

## Sobre o projeto

Este repositório reúne o pré-processamento de sinais eletrofisiológicos (LFP) de ratos de laboratório, registrados com o sistema Intan durante sessões comportamentais.

## Guia de Execução: Pré-processamento LFP com SPARQ

Este documento detalha o fluxo de trabalho atualizado para o pré-processamento dos dados brutos de LFP, integrando o *pipeline* em Python com a ferramenta de deteção de ruído SPARQ no MATLAB. O guia já inclui as configurações e resoluções para jos obstáculos encontrados no ambiente Linux e inconsistências de diretórios.

### Estrutura do repositório

```text
BioInfo-2026.2/
├── eda_lfp_limpa.ipynb      # notebook do pipeline
├── requirements.txt         # dependências Python
└── utils/
    ├── read_intan_data.py   # leitura dos arquivos Intan (.int)
    ├── sparq_lfp.py         # exportação para o SPARQ e leitura dos resultados
    └── rodar_sparq.m        # abre a interface do SPARQ no MATLAB
```

As pastas `dados_eletro/`, `SPARQ/`, `SPARQ_input/` e `saida_preprocessamento/` ficam apenas na sua máquina e não são versionadas (ver `.gitignore`).

## 1. Pré-requisitos e Dependências

Para que o *notebook* execute corretamente as leituras de arquivos Intan, planilhas do Excel e manipulação de matrizes, é obrigatório ter os pacotes instalados no seu ambiente virtual Python (`.venv`).

Abra o terminal, ative o seu ambiente e instale as dependências:

```bash
pip install -r requirements.txt
```

*Nota: O pacote `openpyxl` é estritamente necessário para que o Pandas consiga ler o ficheiro de anotações `.xlsx`.*

## 2. Organização Obrigatória dos Dados

O script extrai automaticamente a identificação do animal baseando-se no nome da pasta onde os arquivos `.int` estão armazenados. Uma estrutura incorreta (como `data/data/SIGNAL/`) causará o erro `unsupported operand type(s) for /: 'PosixPath' and 'float'`.

A sua pasta raiz deve estar organizada exatamente desta forma:

```text
dados_eletro/
├── R3/                      # Pasta com o nome exato do rato
│   ├── D25/                 # Subpastas ou arquivos .int soltos
│   ├── D50/
│   ├── NOR/
│   └── r3_240911_135352.int
├── R4/                      # (Exemplo de outro rato)
└── dados_sessões_comportamento_acontecimentos.xlsx  # Solto na raiz
```

**Atenção aos arquivos vazios:** Arquivos `.int` corrompidos ou com 0 segundos de gravação gerarão o erro `index 0 is out of bounds for axis 0 with size 0`. Você deve excluí-los da pasta.

## 3. Configuração de Caminhos

Os caminhos são lidos de **variáveis de ambiente**, configuradas uma única vez no seu sistema (não é preciso editar o *notebook*). Depois de configurá-las, feche e abra novamente o VSCode/Jupyter.

* **Diretório Base (`BIOINFO_BASE_DIR`):** Aponte para a pasta principal do projeto.
  * *Linux* (no `~/.bashrc`): `export BIOINFO_BASE_DIR='/home/seu_usuario/caminho/para/projeto'`
  * *Windows* (PowerShell): `setx BIOINFO_BASE_DIR "D:\caminho\para\projeto"`
* **Executável do MATLAB (`BIOINFO_MATLAB_EXE`):** Use o caminho absoluto da sua instalação para evitar que o subprocesso falhe ao abrir o programa.
  * *Linux*: `export BIOINFO_MATLAB_EXE='/usr/local/MATLAB/R2026b/bin/matlab'` (ou `/opt/...`)
  * *Windows*: `setx BIOINFO_MATLAB_EXE "C:\Program Files\MATLAB\R2026b\bin\matlab.exe"`

Se as variáveis não forem definidas, o *notebook* usa os valores padrão da primeira célula ("0 — Imports e parâmetros").

> **Atenção!** Antes de rodar o *notebook*, clone o repositório do projeto SPARQ na raiz do projeto, para que fique uma pasta `/SPARQ`:
>
> ```bash
> git clone https://github.com/lafise-ufrn/SPARQ.git
> ```

## 4. Passo a Passo de Execução do Pipeline

### Passo A: Exportação de Dados

1. Com as dependências instaladas e caminhos configurados, rode as células da seção 0 até a 4.1 e, em seguida, a célula de execução do *notebook* ("5 — Execução").
2. O script detectará que as sessões ainda não têm os resultados do SPARQ e exportará os dados brutos de LFP para ficheiros `.mat` na pasta `SPARQ_input`.
3. O MATLAB será aberto automaticamente em segundo plano via subprocesso.
4. Se o script não funcionar, abra o MATLAB e tente rodar o script pela Command Window:

   ```matlab
   addpath('<pasta do projeto>/utils')
   app = rodar_sparq('<pasta do projeto>/SPARQ', '<pasta do projeto>/SPARQ_input')
   ```

### Passo B: Identificação Manual de Ruído no MATLAB

1. Confira se os caminhos na interface se adequam aos do seu dispositivo: a "Pasta de dados" deve ser a pasta `SPARQ_input`.
2. A interface gráfica do SPARQ será iniciada no MATLAB pré-configurada para os seus dados.
3. Selecione cada sessão listada e assinale manualmente o início e o fim de um trecho de sinal limpo para servir de referência.
4. Clique em "Salvar resultados de todas as sessões". Os arquivos `<nome>_clean.mat` serão gerados na subpasta `SPARQ_results`.

### Passo C: Aplicação de Filtros e Máscara

1. Regresse ao Jupyter Notebook e rode novamente a última célula de execução.
2. O código localizará os ficheiros `_clean.mat` que acabou de gerar.
3. Será aplicado o filtro *notch* (55-65 Hz) para remover a interferência da rede elétrica.
4. O sinal é reduzido para 1 kHz (*downsample*) e a máscara de ruído do SPARQ será utilizada para converter as amostras defeituosas em valores nulos (`NaN`), finalizando o pré-processamento do rato selecionado.
5. O resultado de cada sessão é salvo em `saida_preprocessamento/<rato>/<condição>/<rato>__<sessão>/`.
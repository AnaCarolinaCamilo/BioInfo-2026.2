# BioInfo-2026.2

> Projeto executado pela **TAIL UFPB** em cooperação com o **LEMCOG** (Laboratório de Estudos em Memória e Cognição, da Universidade Federal da Paraíba).

<p align="center">
  <img src="assets/TAIL.png" alt="Logo da TAIL UFPB" height="120">
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="assets/LEMCOG.png" alt="Logo do LEMCOG" height="110">
</p>

## Sobre o projeto

Este repositório reúne o pré-processamento de sinais eletrofisiológicos (LFP) de ratos de laboratório, registrados com o sistema Intan durante sessões comportamentais.

## Guia de Execução: Pré-processamento LFP com SPARQ

Este documento detalha o fluxo de trabalho atualizado para o pré-processamento dos dados brutos de LFP, integrando o *pipeline* em Python com a ferramenta de deteção de ruído SPARQ no MATLAB. O guia já inclui as configurações e resoluções para os obstáculos encontrados no ambiente Linux e inconsistências de diretórios.

### Estrutura do repositório

```text
BioInfo-2026.2/
├── eda_lfp_limpa.ipynb      # notebook do pipeline
├── requirements.txt         # dependências Python
└── utils/
    ├── baixar_dados.py      # download dos dados brutos do Drive (rclone)
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

### Download dos dados (rclone)

O script `utils/baixar_dados.py` baixa os `.int` de cada rato para `dados_eletro/<rato>/` usando o [rclone](https://rclone.org/) com a sua conta Google.

1. **Instale o rclone:** `winget install Rclone.Rclone` (Windows) ou `curl https://rclone.org/install.sh | sudo bash` (Linux).
2. **Conecte sua conta Google** (uma vez). Rode o comando abaixo, faça login no navegador que vai abrir com a conta que tem acesso à pasta dos ratos e clique em **Permitir**:

   ```bash
   rclone config create gdrive drive scope=drive.readonly
   ```

   Para conferir, `rclone listremotes` deve mostrar `gdrive:`.

   <details>
   <summary>Prefere configurar passo a passo, ou deu algum problema?</summary>

   **Passo a passo** com `rclone config` (responda cada pergunta e tecle Enter):

   | O rclone pergunta | Responda |
   |---|---|
   | `n/s/q>` (ou `e/n/d/r/c/s/q>`, se já houver outro remote) | `n` (novo remote) |
   | `name>` | `gdrive` |
   | `Storage>` | `drive` (Google Drive) |
   | `client_id>` e `client_secret>` | deixe em branco (só Enter) |
   | `scope>` | `2` (`drive.readonly`, só leitura) |
   | `service_account_file>` | deixe em branco |
   | `Edit advanced config?` | `n` |
   | `Continue using the shared client_id anyway?` | `y` |
   | `Use web browser to automatically authenticate?` | `y` e faça login no navegador |
   | `Configure this as a Shared Drive (Team Drive)?` | `n` |
   | `Keep this "gdrive" remote?` | `y`, depois `q` para sair |

   **Problemas comuns:**

   * *O navegador não abriu:* copie o endereço `http://127.0.0.1:53682/...` que aparece no terminal e abra no navegador.
   * *Computador sem navegador (servidor Linux):* responda `n` em "Use web browser...", rode `rclone authorize "drive"` num computador com navegador e cole o resultado no terminal do servidor.
   * *"Remote 'gdrive' não configurado":* o nome do remote é diferente. Veja com `rclone listremotes` e passe `--remote <nome>` ao script.
   * *Erro 404 / "não foi possível listar a pasta":* a conta usada no login não tem acesso à pasta. Peça acesso a quem compartilhou ou refaça a conexão com `rclone config reconnect gdrive:`.
   * *Erro de cota ou aviso de que o `client_id` compartilhado do rclone foi desativado:* crie um `client_id` próprio seguindo o [guia do rclone](https://rclone.org/drive/#making-your-own-client-id) e informe-o nas perguntas `client_id>` e `client_secret>`.

   </details>
3. **Baixe** informando o link da pasta dos ratos ([pasta atual](https://drive.google.com/drive/folders/1-5FCUo-BOvnJ_217twbcyIjEVflm2NQu)):

```bash
python utils/baixar_dados.py --pasta <link> --listar   # ratos disponíveis
python utils/baixar_dados.py --pasta <link> R4         # baixa um rato (ou R1 R4, ou ALL)
```

Opções úteis: `--dry-run` (só simula), `--filtro "*T[1-4]_*"` (só as sessões de teste) e `--com-videos` (por padrão os vídeos ficam de fora). Para não repetir o link, defina a variável de ambiente `BIOINFO_DRIVE_PASTA`. O script só copia, nunca apaga, e retoma de onde parou se for interrompido. As planilhas `.xlsx` não estão nessa pasta e devem ser copiadas à parte. Espaço por rato: de 26 GB (R6) a 106 GB (R2).

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
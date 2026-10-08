# BioInfo-2026.2

```markdown
# Guia de Execução: Pré-processamento LFP com SPARQ

Este documento detalha o fluxo de trabalho atualizado para o pré-processamento dos dados brutos de LFP, integrando o *pipeline* em Python com a ferramenta de deteção de ruído SPARQ no MATLAB. O guia já inclui as configurações e resoluções para os obstáculos encontrados no ambiente Linux e inconsistências de diretórios.

## 1. Pré-requisitos e Dependências

Para que o *notebook* execute corretamente as leituras de arquivos Intan, planilhas do Excel e manipulação de matrizes, é obrigatório ter os pacotes instalados no seu ambiente virtual Python (`.venv`).

Abra o terminal, ative o seu ambiente e instale as dependências:
```bash
pip install numpy pandas scipy tqdm h5py openpyxl
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

## 3. Configuração de Caminhos no Notebook

Na primeira célula do *notebook* ("0 — Imports e parâmetros"), ajuste os caminhos para o seu sistema:

* **Diretório Base:** Aponte para a pasta principal do projeto.
* *Linux:* `BASE_DIR = Path('/home/seu_usuario/caminho/para/projeto')`
* *Windows:* `BASE_DIR = Path(r'D:\caminho\para\projeto')`



* **Executável do MATLAB (`MATLAB_EXE`):** Substitua `'matlab'` pelo caminho absoluto da sua instalação para evitar que o subprocesso falhe ao abrir o programa.


* *Linux:* `MATLAB_EXE = '/usr/local/MATLAB/R2026b/bin/matlab'` (ou `/opt/...`)
* *Windows:* `MATLAB_EXE = r'C:\Program Files\MATLAB\R2026b\bin\matlab.exe'`

**Atenção! Antes de rodar o notebook copie o repositório do projeto SPARQ, para que fique uma pasta /SPARQ**



## 4. Passo a Passo de Execução do Pipeline

**Passo A: Exportação de Dados**

1. Com as dependências instaladas e caminhos configurados, rode a primeira célula e, em seguida, a última célula do *notebook* ("5 — Execução").


2. O script detectará que as sessões ainda não têm os resultados do SPARQ e exportará os dados brutos de LFP para ficheiros `.mat` na pasta `SPARQ_input`.



4. O MATLAB será aberto automaticamente em segundo plano via subprocesso.



**Passo B: Identificação Manual de Ruído no MATLAB**

1. Modifique os caminhos para que se adeque aos do seu dispositivo!
2. A interface gráfica do SPARQ será iniciada no MATLAB pré-configurada para os seus dados.
3. Selecione cada sessão listada e assinale manualmente o início e o fim de um trecho de sinal limpo para servir de referência.
4. Clique em "Salvar resultados de todas as sessões". Os arquivos `<nome>_clean.mat` serão gerados na subpasta `SPARQ_results`.

**Passo C: Aplicação de Filtros e Máscara**

1. Regresse ao Jupyter Notebook e rode novamente a última célula de execução.
2. O código localizará os ficheiros `_clean.mat` que acabou de gerar.
3. Será aplicado o filtro *notch* (55-65 Hz) para remover a interferência da rede elétrica.
4. A máscara de ruído do SPARQ será utilizada para converter as amostras defeituosas em valores nulos (`NaN`), finalizando o pré-processamento do rato selecionado.



```

```

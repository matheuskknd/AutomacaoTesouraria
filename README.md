# HemeraRemessa

Branch|CI
---|---
master|<img src="https://gitlab.bancoarbi.com.br/matheus.delgado/HemeraRemessa/badges/master/pipeline.svg" title="Master branch CI status"/>

# Utilitário para envio de remessas a Hemera/Zheus API

Este repositório contém um script python com a capacidade de converter uma tabela com recebíveis de cartão um payload JSON+XML compatível com o que é esperado pela [API Zheus da Hemera](https://zheusapi.docs.apiary.io/#reference/envio-de-arquivos/callback/callback). No intuito de utilizarmos os serviços de recebíveis de cartão da Hemera.

## <a name="python_environment"></a>Python environment

Para garantir que todas as dependências estejam instaladas corretamente, execute os seguintes comandos dentro da raiz do repositório antes de usar o script:

Bash

```bash
python3 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

CMD

```bash
python3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Power Shell

```powershell
python3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Cheque a instalação. O seguinte comando deve mostrar todas as dependências:

```bash
python -m pip freeze
```

## Executando

Já de dentro do *Python Environment* e supondo que o arquivo ```input.xlsx``` seja a entrada, execute o seguinte:

```bash
python hemera.py -i input.xlsx -o output.json
```

Mensagem de ajuda da CLI:

```bash
$ python hemera.py -h
usage: hemera.py [-h] [-i inputFileName] [-o outputFileName]

Conversor da tabela Tecban Pontos de Saque e Troco.

options:
  -h, --help            show this help message and exit
  -i inputFileName, --input inputFileName
                        Arquivo de entrada no formato XLSX. Deve ser legível.
  -o outputFileName, --output outputFileName
                        Arquivo de saída no formato JSON. Deve ser gravável.
```

# Instruções de desenvolvimento

Segue uma lista de instruções que todo código deve seguir para garantir boa legibilidade e manutenibilidade:

* Todo código DEVE ser formatado com [Yapf](https://github.com/google/yapf) ([instruções](#coding_instruction_01));
* Todo código DEVE passar no [Pyright type checking](https://github.com/microsoft/pyright) ([instruções](#coding_instruction_02));
* Todo código DEVE passar no [Pylint static code analysis](https://pylint.pycqa.org/en/latest/) ([instruções](#coding_instruction_03));
* Dependências DEVEM ser declaradas nos arquivos ```requirements.in``` e compiladas com [pip-tools](https://github.com/jazzband/pip-tools) ([instruções](#coding_instruction_04));
* A implantação do programa pode ser feita via [PyInstaller](https://pyinstaller.org/en/stable/) ([instruções](#coding_instruction_05));

## <a name="coding_instruction_01"></a>Code formatting

Todo código DEVE ser formatado com [Yapf](https://github.com/google/yapf) para garantir legibilidade e manutenibilidade apropriada. Execute os seguites comandos para garantir este ponto:

```bash
yapf --style .style.yapf --in-place *.py
```

Para checar se o código já está formatado corretamente execute o seguinte:

```bash
yapf --style .style.yapf --diff *.py
```

Este comando deve retornar "0" em caso de sucesso, ou diferente de "0" do contrário.

## <a name="coding_instruction_02"></a>Type checking

Todo código DEVE passar no [Pyright type checking](https://github.com/microsoft/pyright) para garantir legibilidade e manutenibilidade apropriada. Execute os seguites comandos para garantir este ponto:

```bash
pyright --project pyrightconfig.json
```

Este comando deve retornar "0" em caso de sucesso, ou diferente de "0" do contrário.

## <a name="coding_instruction_03"></a>Static analysis

Todo código DEVE passar no [Pylint static code analysis](https://pylint.pycqa.org/en/latest/) para garantir legibilidade e manutenibilidade apropriada. Execute os seguites comandos para garantir este ponto:

```bash
pylint --errors-only --disable=C,R --rcfile .pylintrc *.py
```

Este comando deve retornar "0" em caso de sucesso, ou diferente de "0" do contrário.

### <a name="coding_instruction_04"></a>Depency declarations

Dependências DEVEM ser declaradas nos arquivos ```requirements.in``` e ```.dev-requirements.in``` e compiladas com [pip-tools](https://github.com/jazzband/pip-tools), assim as dependências baixadas no futuro serão determinísticas. Execute os seguintes comandos após atualizar a declaração de dependências e antes de fazer um *commit*:

```bash
python -m piptools compile --quiet --output-file=requirements.txt requirements.in
python -m piptools compile --quiet --output-file=.dev-requirements.txt .dev-requirements.in
```

Não se esqueça de executar os seguintes comandos para atualizar o *Python Environment* antes de começar a desenvolver:

Bash

```bash
python3 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r .dev-requirements.txt
```

CMD

```bash
python3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r .dev-requirements.txt
```

Power Shell

```powershell
python3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r ".dev-requirements.txt"
```

Cheque a instalação. O seguinte comando deve mostrar todas as dependências:

```bash
python -m pip freeze
```

### <a name="coding_instruction_05"></a>Deploy

O módulo pode ser implantado na forma de um executável utilizando o [PyInstaller](https://pyinstaller.org/en/stable/). Execute os seguites comandos para gerar o executável:

```bash
python -m PyInstaller pyinstaller_entry.py --onefile --windowed --name HemeraRemessa_v0.2.1
```

Mais informações a respeito de como utilizar e depurar erros de implantação podem ser obtidas [neste tutorial](https://realpython.com/pyinstaller-python/).

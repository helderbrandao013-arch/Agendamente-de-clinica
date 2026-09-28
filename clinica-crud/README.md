# Agenda de atendimentos da clínica

Projeto da disciplina **Desenvolvimento Rápido de Aplicações**, implementado com Python, Streamlit e SQLite.

## Problema e usuários

Uma clínica pequena recebe pedidos por telefone e WhatsApp. Sem uma agenda central, pode marcar dois pacientes com o mesmo profissional no mesmo horário e perder o acompanhamento das faltas.

A aplicação centraliza os cadastros, a agenda e os relatórios. A recepcionista é a usuária principal; os profissionais consultam a organização dos atendimentos, e os pacientes são beneficiados pela redução de conflitos de horário.

O escopo segue o projeto de clínica do [material de referência da disciplina](https://projetos-crud-python-rad.ajr164694.chatgpt.site/), com o modelo e as regras detalhados no enunciado. A implementação usa apenas Python, Streamlit e SQLite, com pytest para os testes.

## Como executar

Use **Python 3.10 ou superior**. O projeto foi validado com Python 3.13.13, Streamlit 1.64.0 e pytest 9.1.1 no Windows. SQLite já acompanha a instalação padrão do Python.

Extraia o projeto e abra um terminal na pasta que contém `app.py`, `db.py` e `requirements.txt`.

### Windows / PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Os comandos usam diretamente o Python do ambiente virtual; não é necessário mudar a política de execução do PowerShell para ativá-lo.

### Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python seed.py
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

Abra o endereço informado pelo Streamlit, normalmente [http://localhost:8501](http://localhost:8501). Para encerrar, pressione `Ctrl+C` no terminal.

Com o ambiente virtual ativado, os comandos equivalentes são:

```bash
pip install -r requirements.txt
python seed.py
pytest -q
streamlit run app.py --server.address 127.0.0.1
```

O comando `seed.py` é opcional. Sem ele, a aplicação inicia vazia e cria as tabelas automaticamente. O banco padrão é `clinica.db`, ao lado de `db.py`, e os dados persistem entre execuções.

### Dados de demonstração

`seed.py` cria **5 pacientes, 3 profissionais e 7 atendimentos fictícios**. Ele informa no terminal as datas que devem ser selecionadas na agenda:

- Um dia útil recente tem exemplos de agendado, realizado, cancelado e falta.
- O dia útil atual ou seguinte tem três próximos agendamentos.
- No período que inclui todos os exemplos, o relatório inicial mostra total 7, cancelados 1 e taxa de faltas 50%.

Se já houver pacientes ou profissionais, o script informa que o banco está preenchido e não adiciona, substitui ou exclui dados. Os testes usam arquivos temporários próprios e não modificam o banco da demonstração.

Para usar outro arquivo SQLite no PowerShell:

```powershell
$env:CLINICA_DB = "C:\caminho\existente\demonstracao.db"
.\.venv\Scripts\python.exe seed.py
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Também é possível executar `python seed.py --banco caminho/do/arquivo.db`; essa opção tem prioridade sobre `CLINICA_DB` somente para o script de carga. A pasta de destino deve existir.

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `db.py` | Toda a persistência, validação e regras de negócio; sem import de Streamlit. |
| `app.py` | Interface com as cinco páginas e mensagens amigáveis de `ErroDeNegocio`. |
| `test_db.py` | 93 casos de teste para regras, CRUD, SQL injection e concorrência. |
| `test_app.py` | 18 casos de integração com Streamlit AppTest, incluindo confirmações da RN5. |
| `seed.py` | Carga de dados fictícios em banco vazio. |
| `requirements.txt` | Versões das dependências utilizadas. |
| `.streamlit/config.toml` | Tema visual e configuração de telemetria do Streamlit. |
| `.gitignore` | Evita versionar bancos locais, caches e ambientes virtuais. |
| `README.md` | Problema, requisitos, modelo, decisões e instruções. |

## Requisitos funcionais e uso das páginas

| Página | Operações disponíveis |
|---|---|
| Agenda do dia | Listar por data e profissional, reagendar, trocar profissional, mudar situação, editar serviço/observação e excluir atendimento incorreto com confirmação. |
| Novo agendamento | Selecionar paciente, profissional, dia, horário livre, serviço e observação administrativa. |
| Pacientes | Cadastrar, listar, buscar por nome/telefone, editar e excluir quando não houver histórico. |
| Profissionais | Cadastrar, listar, editar e excluir quando não houver histórico. |
| Relatórios | Consultar total, cancelados, faltas, taxa de faltas e faltas por profissional em um período. |

Para alterar um atendimento, selecione sua data na **Agenda do dia**, escolha o registro em **Atendimento para editar** e use **Salvar alterações do atendimento**. Mudar a situação para **Cancelado** mostra uma caixa de confirmação; o botão fica desabilitado enquanto ela não for marcada.

As exclusões ficam em um painel próprio. A pessoa deve marcar uma confirmação que identifica o registro e pressionar o botão de exclusão definitiva. A exclusão de atendimento destina-se a registro lançado por engano; cancelar mantém o registro para o relatório.

## Modelo de dados

O modelo solicitado foi preservado, com três tabelas:

```text
pacientes
  id               INTEGER, chave primária
  nome             TEXT, obrigatório
  telefone         TEXT, obrigatório
  criado_em        TEXT, data/hora de criação

profissionais
  id               INTEGER, chave primária
  nome             TEXT, obrigatório
  especialidade    TEXT, obrigatória

atendimentos
  id               INTEGER, chave primária
  paciente_id      INTEGER, FK → pacientes.id
  profissional_id  INTEGER, FK → profissionais.id
  data_hora        TEXT, formato AAAA-MM-DD HH:MM
  servico          TEXT, catálogo administrativo
  situacao         TEXT, agendado | realizado | cancelado | falta
  observacao       TEXT, catálogo administrativo; vazio permitido
```

Cada paciente e cada profissional pode estar vinculado a vários atendimentos. Cada atendimento possui exatamente um paciente e um profissional. As chaves estrangeiras usam `ON DELETE RESTRICT`, e `PRAGMA foreign_keys = ON` é ativado em cada conexão.

## Regras de negócio implementadas

| Regra | Implementação e comportamento |
|---|---|
| RN1 | Um profissional não pode ter dois atendimentos não cancelados no mesmo horário. Há validação e índice único parcial no SQLite. |
| RN2 | A mesma proteção existe para o paciente, inclusive entre profissionais diferentes. |
| RN3 | Cancelados liberam a vaga. Reativar para agendado, realizado ou falta exige disponibilidade do paciente e do profissional. |
| RN4 | Qualquer atendimento existente, inclusive cancelado, impede excluir paciente/profissional. Seus cadastros continuam editáveis. |
| RN5 | Cancelamento e exclusão exigem caixa de confirmação na interface. O banco também exige `confirmado=True`. |
| RN6 | O cadastro do paciente contém somente nome, telefone e os metadados previstos. Serviço e observação aceitam exclusivamente opções administrativas; a interface orienta a não registrar informações clínicas. |

Todas as entradas externas em SQL são vinculadas por parâmetros `?`. Instruções de criação de tabelas, índices e consultas sem filtros são fixas. Nenhuma entrada é concatenada ou interpolada como comando SQL.

## Decisões adotadas

1. **Grade confirmada:** segunda a sexta, 08h30 às 18h, atendimentos de 20 minutos. São 28 opções: 08h30, 08h50, 09h10, …, 17h30. O último termina às 17h50; iniciar às 17h50 excederia o fechamento. A duração é uma constante, sem adicionar coluna ao modelo.
2. **Horário local:** `data_hora` representa o horário local da clínica, com precisão de minuto e formato validado. A grade é validada também no banco, nas operações da API.
3. **Situações que ocupam vaga:** agendado, realizado e falta. Somente cancelado libera a vaga. Reagendamento desconsidera o próprio registro na verificação do horário.
4. **Disponibilidade:** o formulário considera simultaneamente a agenda do paciente e do profissional. A operação revalida a vaga ao salvar. Se outra sessão ocupar a seleção anterior, a interface pede uma nova seleção.
5. **Concorrência:** cada operação abre e fecha sua conexão. Escritas usam `BEGIN IMMEDIATE`, validam e gravam na mesma transação. Índices únicos parciais também impedem duplicidade no SQLite. Qualquer falha desfaz a operação inteira.
6. **Taxa de faltas confirmada:** `faltas / (realizados + faltas) * 100`, arredondada para duas casas. Agendados e cancelados ficam fora do denominador. Quando ele é zero, a taxa é 0%.
7. **Período do relatório:** usa a data do atendimento, incluindo integralmente as datas inicial e final. O total inclui todas as situações. A tabela de faltas inclui profissionais com zero ocorrências.
8. **Histórico:** a proteção considera os atendimentos que existem no banco. Excluir um lançamento incorreto o remove dos relatórios; se não restar nenhum atendimento vinculado, o cadastro pode ser excluído. Não há tabela de auditoria adicional.
9. **Busca:** nome e telefone aceitam trechos literais. A busca por nome ignora maiúsculas/minúsculas com `casefold`, inclusive em nomes acentuados. Apóstrofos, `%`, `_` e textos de SQL são tratados como dados.
10. **Privacidade:** serviço e observação usam listas fechadas, conforme escolha confirmada. Campos de nome, telefone e especialidade devem ser usados somente para sua finalidade. O sistema não faz classificação semântica do conteúdo desses campos. Os exemplos e testes usam dados fictícios.

### Catálogos administrativos

Serviços: `Consulta`, `Retorno` e `Atendimento administrativo`.

Observações: sem observação, `Agendado por telefone`, `Agendado por WhatsApp`, `Confirmado por telefone`, `Confirmado por WhatsApp` e `Aguardando confirmação`.

Os catálogos são validados pela API e por restrições `CHECK` no SQLite. Não existem campos para sintomas, diagnóstico, resultados de exames ou tratamento. Não foram incluídos login, autenticação nem módulos adicionais.

## Validação realizada

O desenvolvimento seguiu a ordem: banco → testes do banco → interface → verificação das cinco páginas no navegador → documentação.

Resultado da suíte conjunta após o ajuste final da interface:

```text
111 passed in 14.67s
```

Os 93 testes de banco cobrem CRUD, RN1–RN6, conflito de paciente e profissional, reativação, registros cancelados, preservação de histórico, validações, relatórios, tentativas de SQL injection, busca Unicode e duas conexões disputando a mesma vaga. Os 18 testes AppTest verificam a interface e comprovam que os botões destrutivos permanecem desabilitados antes da confirmação.

Na preparação do ambiente de desenvolvimento, o sandbox do Windows bloqueou os diretórios temporários do pytest. A suíte foi reexecutada com as permissões de execução necessárias e passou; isso não exigiu alteração das regras nem dos testes.

### Verificação manual no navegador

| Página | Evidência observada |
|---|---|
| Agenda do dia | Agenda de 28/09/2026 carregada; cancelamento bloqueado antes da confirmação e concluído após marcá-la. |
| Novo agendamento | Horário cancelado reapareceu; novo agendamento bem-sucedido o retirou da lista de vagas. |
| Pacientes | Cadastro, busca, edição de telefone e exclusão confirmada de registro fictício; busca com `' OR 1=1 --` retornou zero resultados. |
| Profissionais | Cadastro fictício concluído; tentativa de excluir profissional com histórico retornou mensagem amigável e preservou o registro. |
| Relatórios | Período com quatro atendimentos mostrou um cancelado, uma falta e taxa de 50%; tabela e gráfico por profissional renderizados. |

O teste visual também identificou um painel de exclusão que fechava durante uma atualização. O painel recebeu identificação estável, e seu comportamento foi verificado novamente no navegador. Os dados utilizados nessa verificação ficaram em um banco de teste separado.

### Roteiro para demonstração em sala

1. Execute `seed.py` e anote as datas exibidas.
2. Abra a agenda do próximo dia útil e filtre por profissional.
3. Tente escolher um horário ocupado no formulário: ele não aparece para os participantes selecionados.
4. Cancele um atendimento com confirmação e veja a vaga reaparecer.
5. Ocupe a vaga com outro registro e tente reativar o cancelado; será necessário escolher outra vaga.
6. Edite serviço e observação usando as opções administrativas.
7. Tente excluir um paciente/profissional com histórico e observe o bloqueio.
8. Abra o período indicado pelo seed nos relatórios e explique o cálculo de 50%.
9. Apresente a execução de `pytest -q` e a separação entre regras em `db.py` e interface em `app.py`.

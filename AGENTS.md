# Agenda de atendimentos da clínica

Aplicação acadêmica em `clinica-crud/`: Python 3.10+, Streamlit 1.64 e SQLite, testes com pytest. Escopo, regras RN1–RN6 e decisões: `clinica-crud/README.md`.

## Comandos (em `clinica-crud/`, Windows/PowerShell)

- Instalar: `python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt`
- Dados fictícios: `.\.venv\Scripts\python.exe seed.py`
- Testes: `.\.venv\Scripts\python.exe -m pytest -q`
- Executar: `.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1`
- Lint, tipos e build: não existem neste projeto.

## Limites do código

- `db.py` concentra persistência, validação e regras; não importa Streamlit. `app.py` só apresenta e chama `BancoClinica`.
- Erros para o usuário são `ErroDeNegocio`. SQL sempre com parâmetros `?`; nada de interpolar entradas.
- Cada operação abre sua conexão; escritas usam `BEGIN IMMEDIATE`. Preserve os índices únicos parciais (RN1/RN2).
- Privacidade (RN6): nenhum campo clínico. Serviço e observação são catálogos fechados validados no banco.
- Cancelamento e exclusão exigem `confirmado=True` na API e caixa de confirmação na interface (RN5).

## Acordos de trabalho

- Leia o código e o README antes de editar; faça a menor mudança completa e reutilize os padrões existentes.
- Toda regra nova ganha teste em `test_db.py`; todo fluxo de tela, em `test_app.py` (AppTest, banco temporário).
- Testes nunca tocam `clinica.db`; use `tmp_path` e `CLINICA_DB`. Dados de exemplo são sempre fictícios.
- Atualize `clinica-crud/README.md` junto com mudanças de comportamento, comandos ou modelo.
- Não publique, não envie mensagens a terceiros e não apague o banco de demonstração sem pedido explícito.

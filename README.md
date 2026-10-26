<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="clinica-crud/assets/logo-nome-escuro.svg">
    <img src="clinica-crud/assets/logo-nome-claro.svg" alt="Clínica · Agenda de atendimentos" width="360">
  </picture>
</p>

<p align="center">
  Agenda de atendimentos para clínicas pequenas: sem horários duplicados, com controle de faltas e lembretes pelo WhatsApp.
</p>

<p align="center">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Streamlit 1.64" src="https://img.shields.io/badge/Streamlit-1.64-FF4B4B?logo=streamlit&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-embutido-003B57?logo=sqlite&logoColor=white">
  <img alt="125 testes com pytest" src="https://img.shields.io/badge/testes-125%20passando-16857d?logo=pytest&logoColor=white">
</p>

---

Trabalho da disciplina **Desenvolvimento Rápido de Aplicações em Python**. A recepcionista centraliza pacientes, profissionais e agenda em um só lugar, e a clínica deixa de marcar dois pacientes no mesmo horário com o mesmo profissional.

## Funcionalidades

| | Página | O que faz |
|---|---|---|
| 🗓️ | **Agenda do dia** | Atendimentos por data e profissional, grade de horários livres/ocupados, mudança de situação, reagendamento e lembrete pelo WhatsApp. |
| ✅ | **Novo agendamento** | Mostra só os horários livres para o paciente **e** o profissional; sem vaga, sugere o próximo dia disponível. |
| 👥 | **Pacientes** | Cadastro com nome e telefone, busca, edição e histórico de atendimentos com total de faltas. |
| 🩺 | **Profissionais** | Cadastro e edição de profissionais e especialidades. |
| 📊 | **Relatórios** | Total, cancelados, faltas e taxa de faltas por período, com gráfico por profissional. |

Outros destaques:

- **Tema claro e escuro**: segue o sistema e pode ser trocado no menu ⋮ do app.
- **Sem conflitos de horário**: regras validadas no código e garantidas por índices únicos no SQLite, inclusive com duas recepcionistas salvando ao mesmo tempo.
- **Privacidade**: somente dados administrativos; serviço e observação são listas fechadas, sem campos clínicos.
- **Ações seguras**: cancelamento e exclusão exigem confirmação explícita.

## Como executar

Requer **Python 3.10 ou superior**. No Windows (PowerShell), dentro da pasta `clinica-crud`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe seed.py          # opcional: dados fictícios de demonstração
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

No Linux/macOS, troque `.\.venv\Scripts\python.exe` por `.venv/bin/python`. O app abre em <http://localhost:8501>.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

São 125 testes: regras de negócio, CRUD, SQL injection, concorrência e a interface com Streamlit AppTest, sempre em bancos temporários.

## Estrutura

```text
clinica-crud/
├── app.py              Interface Streamlit (5 páginas)
├── db.py               Banco SQLite e regras de negócio (sem Streamlit)
├── seed.py             Dados fictícios de demonstração
├── test_db.py          Testes das regras e do banco
├── test_app.py         Testes da interface
├── assets/             Logo do projeto
└── .streamlit/         Temas claro e escuro
```

A documentação completa — modelo de dados, regras RN1–RN6 e decisões — está em [`clinica-crud/README.md`](clinica-crud/README.md).

"""Integração da interface Streamlit, incluindo as confirmações da RN5.

AppTest executa a interface contra um SQLite temporário, sem abrir um navegador.
Os testes de navegação visual no navegador complementam esta suíte.
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from db import BancoClinica, ErroDeNegocio


ARQUIVO_APP = Path(__file__).with_name("app.py")
DIA = date(2026, 9, 28)


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    caminho = tmp_path / "interface.db"
    monkeypatch.setenv("CLINICA_DB", str(caminho))
    banco = BancoClinica(caminho)
    banco.inicializar()
    return banco


@pytest.fixture
def cadastros(ambiente):
    return {
        "p1": ambiente.cadastrar_paciente("Ana Fictícia", "85999990001"),
        "p2": ambiente.cadastrar_paciente("Beto Fictício", "85999990002"),
        "f1": ambiente.cadastrar_profissional("Alice Fictícia", "Clínica geral"),
        "f2": ambiente.cadastrar_profissional("Bruno Fictício", "Clínica geral"),
    }


def elemento(elementos, rotulo):
    correspondentes = [e for e in elementos if e.label == rotulo]
    assert len(correspondentes) == 1, f"Esperado um elemento com o rótulo {rotulo!r}."
    return correspondentes[0]


def abrir(pagina):
    app = AppTest.from_file(str(ARQUIVO_APP), default_timeout=15).run()
    assert not app.exception
    app.sidebar.radio[0].set_value(pagina).run()
    assert not app.exception
    return app


def abrir_agenda():
    app = abrir("Agenda do dia")
    elemento(app.date_input, "Data da agenda").set_value(DIA).run()
    assert not app.exception
    return app


def marcar_checkbox_por_prefixo(app, prefixo):
    correspondentes = [c for c in app.checkbox if c.label.startswith(prefixo)]
    assert len(correspondentes) == 1
    correspondentes[0].check().run()


@pytest.mark.parametrize("pagina", ["Agenda do dia", "Novo agendamento", "Pacientes", "Profissionais", "Relatórios"])
def test_cinco_paginas_vazias_abrem_sem_excecao(ambiente, pagina):
    app = abrir(pagina)
    assert app.title[0].value == pagina
    assert not app.exception
    assert not app.error
    assert app.info


def test_cadastrar_editar_e_buscar_paciente_pela_interface(ambiente):
    app = abrir("Pacientes")
    elemento(app.text_input, "Nome do paciente").set_value("Álvaro Fictício")
    elemento(app.text_input, "Telefone").set_value("85999990003")
    elemento(app.button, "Cadastrar paciente").click().run()
    assert not app.exception
    assert app.success
    paciente = ambiente.listar_pacientes()[0]
    assert paciente["nome"] == "Álvaro Fictício"

    elemento(app.text_input, "Nome").set_value("Álvaro Atualizado")
    elemento(app.text_input, "Telefone atualizado").set_value("85999990004")
    elemento(app.button, "Salvar paciente").click().run()
    assert not app.exception
    assert ambiente.obter_paciente(paciente["id"])["telefone"] == "85999990004"
    elemento(app.text_input, "Buscar por nome ou telefone").set_value("álvaro").run()
    assert len(app.dataframe) == 1
    assert app.dataframe[0].value.iloc[0]["Nome"] == "Álvaro Atualizado"
    elemento(app.text_input, "Buscar por nome ou telefone").set_value("' OR 1=1 --").run()
    assert not app.exception
    assert len(app.dataframe) == 0
    assert len(ambiente.listar_pacientes()) == 1


def test_cadastrar_e_editar_profissional_pela_interface(ambiente):
    app = abrir("Profissionais")
    elemento(app.text_input, "Nome do profissional").set_value("Alice Fictícia")
    elemento(app.text_input, "Especialidade").set_value("Clínica geral")
    elemento(app.button, "Cadastrar profissional").click().run()
    assert not app.exception
    assert app.success
    profissional = ambiente.listar_profissionais()[0]

    elemento(app.text_input, "Nome").set_value("Alice Atualizada")
    elemento(app.text_input, "Especialidade atualizada").set_value("Pediatria")
    elemento(app.button, "Salvar profissional").click().run()
    assert not app.exception
    assert ambiente.obter_profissional(profissional["id"])["nome"] == "Alice Atualizada"
    assert ambiente.obter_profissional(profissional["id"])["especialidade"] == "Pediatria"


def test_campos_obrigatorios_invalidos_mostram_erro_amigavel(ambiente):
    app = abrir("Pacientes")
    elemento(app.button, "Cadastrar paciente").click().run()
    assert not app.exception
    assert any("Informe" in e.value for e in app.error)
    assert ambiente.listar_pacientes() == []


def test_novo_agendamento_mostra_apenas_horarios_livres_para_ambos(ambiente, cadastros):
    # Ana ocupa 08:30 com Bruno; Alice ocupa 08:50 com Beto.
    ambiente.agendar_atendimento(cadastros["p1"], cadastros["f2"], "2026-09-28 08:30", "Consulta")
    ambiente.agendar_atendimento(cadastros["p2"], cadastros["f1"], "2026-09-28 08:50", "Consulta")
    app = abrir("Novo agendamento")
    elemento(app.date_input, "Dia do atendimento").set_value(DIA).run()
    elemento(app.selectbox, "Paciente").select(cadastros["p1"]).run()
    elemento(app.selectbox, "Profissional").select(cadastros["f1"]).run()
    horarios = elemento(app.selectbox, "Horário livre")
    assert "08:30" not in horarios.options
    assert "08:50" not in horarios.options
    assert "09:10" in horarios.options
    assert len(horarios.options) == 26
    assert elemento(app.button, "Agendar atendimento").disabled

    horarios.select("09:10").run()
    elemento(app.selectbox, "Serviço").select("Retorno").run()
    elemento(app.selectbox, "Observação administrativa").select("Agendado por telefone").run()
    assert not elemento(app.button, "Agendar atendimento").disabled
    elemento(app.button, "Agendar atendimento").click().run()
    assert not app.exception
    assert app.success
    novos = [a for a in ambiente.listar_atendimentos(DIA) if a["data_hora"].endswith("09:10")]
    assert len(novos) == 1
    assert novos[0]["paciente_id"] == cadastros["p1"]
    assert novos[0]["profissional_id"] == cadastros["f1"]
    assert novos[0]["servico"] == "Retorno"
    assert novos[0]["observacao"] == "Agendado por telefone"


def test_fim_de_semana_nao_permite_agendar(ambiente, cadastros):
    app = abrir("Novo agendamento")
    elemento(app.date_input, "Dia do atendimento").set_value(date(2026, 10, 3)).run()
    assert not app.exception
    assert elemento(app.selectbox, "Horário livre").options == []
    assert elemento(app.selectbox, "Horário livre").disabled
    assert elemento(app.button, "Agendar atendimento").disabled
    assert any("segunda a sexta" in info.value for info in app.info)


def test_rn5_cancelar_so_fica_habilitado_apos_checkbox(ambiente, cadastros):
    atendimento_id = ambiente.agendar_atendimento(cadastros["p1"], cadastros["f1"], "2026-09-28 08:30", "Consulta")
    app = abrir_agenda()
    elemento(app.selectbox, "Situação").select("cancelado").run()
    assert elemento(app.button, "Salvar alterações do atendimento").disabled
    assert ambiente.obter_atendimento(atendimento_id)["situacao"] == "agendado"
    marcar_checkbox_por_prefixo(app, "Confirmo o cancelamento")
    assert not elemento(app.button, "Salvar alterações do atendimento").disabled
    elemento(app.button, "Salvar alterações do atendimento").click().run()
    assert not app.exception
    assert ambiente.obter_atendimento(atendimento_id)["situacao"] == "cancelado"
    assert "08:30" in ambiente.horarios_livres(DIA, cadastros["p1"], cadastros["f1"])


@pytest.mark.parametrize("entidade,pagina", [("paciente", "Pacientes"), ("profissional", "Profissionais"), ("atendimento", "Agenda do dia")])
def test_rn5_excluir_so_fica_habilitado_apos_checkbox(ambiente, cadastros, entidade, pagina):
    if entidade == "atendimento":
        registro_id = ambiente.agendar_atendimento(cadastros["p1"], cadastros["f1"], "2026-09-28 08:30", "Consulta")
        app = abrir_agenda()
    else:
        registro_id = cadastros["p1" if entidade == "paciente" else "f1"]
        app = abrir(pagina)
    rotulo = f"Excluir {entidade} definitivamente"
    obter = getattr(ambiente, "obter_" + entidade)
    assert elemento(app.button, rotulo).disabled
    assert obter(registro_id)["id"] == registro_id
    marcar_checkbox_por_prefixo(app, "Confirmo a exclusão")
    assert not elemento(app.button, rotulo).disabled
    elemento(app.button, rotulo).click().run()
    assert not app.exception
    assert app.success
    with pytest.raises(ErroDeNegocio, match="não encontrado"):
        obter(registro_id)


@pytest.mark.parametrize("entidade,pagina", [("paciente", "Pacientes"), ("profissional", "Profissionais")])
def test_rn4_interface_preserva_cadastro_com_historico(ambiente, cadastros, entidade, pagina):
    atendimento_id = ambiente.agendar_atendimento(cadastros["p1"], cadastros["f1"], "2026-09-28 08:30", "Consulta")
    ambiente.atualizar_atendimento(atendimento_id, situacao="cancelado", confirmado=True)
    app = abrir(pagina)
    marcar_checkbox_por_prefixo(app, "Confirmo a exclusão")
    elemento(app.button, f"Excluir {entidade} definitivamente").click().run()
    assert not app.exception
    assert any("histórico" in erro.value for erro in app.error)
    registro_id = cadastros["p1" if entidade == "paciente" else "f1"]
    assert getattr(ambiente, "obter_" + entidade)(registro_id)["id"] == registro_id
    assert ambiente.obter_atendimento(atendimento_id)["situacao"] == "cancelado"


def test_relatorio_exibe_taxa_cinquenta_por_cento_e_periodo_invalido(ambiente, cadastros):
    for hora, situacao in [("08:30", "realizado"), ("08:50", "falta"), ("09:10", "cancelado"), ("09:30", "agendado")]:
        atendimento_id = ambiente.agendar_atendimento(cadastros["p1"], cadastros["f1"], f"2026-09-28 {hora}", "Consulta")
        ambiente.atualizar_atendimento(atendimento_id, situacao=situacao, confirmado=True)
    app = abrir("Relatórios")
    elemento(app.date_input, "Data inicial").set_value(DIA)
    elemento(app.date_input, "Data final").set_value(DIA).run()
    assert not app.exception
    assert elemento(app.metric, "Total de atendimentos").value == "4"
    assert elemento(app.metric, "Cancelados").value == "1"
    assert elemento(app.metric, "Taxa de faltas").value == "50,00%"
    elemento(app.date_input, "Data inicial").set_value(date(2026, 9, 29)).run()
    assert not app.exception
    assert any("posterior" in erro.value for erro in app.error)
    assert len(app.metric) == 0


def test_horario_ocupado_por_outra_sessao_exige_nova_selecao(ambiente, cadastros):
    app = abrir("Novo agendamento")
    elemento(app.date_input, "Dia do atendimento").set_value(DIA).run()
    elemento(app.selectbox, "Horário livre").select("08:30").run()
    ambiente.agendar_atendimento(cadastros["p2"], cadastros["f1"], "2026-09-28 08:30", "Consulta")
    app.run()
    assert not app.exception
    assert any("ficou indisponível" in aviso.value for aviso in app.warning)
    assert elemento(app.button, "Agendar atendimento").disabled
    assert len(ambiente.listar_atendimentos(DIA)) == 1

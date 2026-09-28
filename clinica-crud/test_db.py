"""Testes de comportamento, sem interface e sem tocar no banco da demonstração.

Cada teste recebe um arquivo SQLite novo em tmp_path. Execute: pytest -q.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
import sqlite3
from threading import Barrier

import pytest

from db import BancoClinica, ErroDeNegocio, OBSERVACOES, SERVICOS, horarios_do_dia


DIA = "2026-09-28"  # Segunda-feira; data fixa para testes reproduzíveis.
INSTANTE = DIA + " 08:30"


@pytest.fixture
def banco(tmp_path):
    instancia = BancoClinica(tmp_path / "teste.db")
    instancia.inicializar()
    return instancia


@pytest.fixture
def cadastros(banco):
    return {
        "p1": banco.cadastrar_paciente("Ana Exemplo", "85999990001"),
        "p2": banco.cadastrar_paciente("Beto Exemplo", "85999990002"),
        "p3": banco.cadastrar_paciente("Carla Exemplo", "85999990003"),
        "f1": banco.cadastrar_profissional("Alice Exemplo", "Clínica geral"),
        "f2": banco.cadastrar_profissional("Bruno Exemplo", "Clínica geral"),
        "f3": banco.cadastrar_profissional("Celia Exemplo", "Clínica geral"),
    }


def agendar(banco, ids, *, paciente="p1", profissional="f1", instante=INSTANTE):
    return banco.agendar_atendimento(ids[paciente], ids[profissional], instante, SERVICOS[0])


def mudar_situacao(banco, atendimento_id, situacao):
    banco.atualizar_atendimento(atendimento_id, situacao=situacao, confirmado=True)


def test_inicializar_novamente_preserva_dados(banco):
    paciente_id = banco.cadastrar_paciente("Ana", "123")
    banco.inicializar()
    assert banco.obter_paciente(paciente_id)["nome"] == "Ana"


def test_crud_paciente_e_busca_por_nome_telefone(banco):
    paciente_id = banco.cadastrar_paciente("  Ana Exemplo  ", " 85999990001 ")
    original = banco.obter_paciente(paciente_id)
    assert original["nome"] == "Ana Exemplo"
    assert original["telefone"] == "85999990001"
    assert original["criado_em"]
    assert banco.listar_pacientes("aNA") == [original]
    assert banco.listar_pacientes("0001") == [original]
    assert banco.listar_pacientes("inexistente") == []

    banco.editar_paciente(paciente_id, "Ana Silva", "85999990002")
    atualizado = banco.obter_paciente(paciente_id)
    assert atualizado["nome"] == "Ana Silva"
    assert atualizado["telefone"] == "85999990002"
    assert atualizado["criado_em"] == original["criado_em"]
    banco.excluir_paciente(paciente_id, confirmado=True)
    assert banco.listar_pacientes() == []
    with pytest.raises(ErroDeNegocio, match="Paciente não encontrado"):
        banco.obter_paciente(paciente_id)


def test_crud_profissional(banco):
    profissional_id = banco.cadastrar_profissional(" Alice ", " Clínica geral ")
    assert banco.listar_profissionais() == [
        {"id": profissional_id, "nome": "Alice", "especialidade": "Clínica geral"}
    ]
    banco.editar_profissional(profissional_id, "Alice Silva", "Pediatria")
    assert banco.obter_profissional(profissional_id)["especialidade"] == "Pediatria"
    banco.excluir_profissional(profissional_id, confirmado=True)
    assert banco.listar_profissionais() == []
    with pytest.raises(ErroDeNegocio, match="Profissional não encontrado"):
        banco.obter_profissional(profissional_id)


@pytest.mark.parametrize("metodo,args", [
    ("cadastrar_paciente", ("", "123")),
    ("cadastrar_paciente", ("Ana", "  ")),
    ("cadastrar_paciente", (None, "123")),
    ("cadastrar_profissional", ("  ", "Clínica geral")),
    ("cadastrar_profissional", ("Alice", "")),
])
def test_cadastros_exigem_campos_obrigatorios(banco, metodo, args):
    with pytest.raises(ErroDeNegocio, match="Informe"):
        getattr(banco, metodo)(*args)
    assert banco.listar_pacientes() == []
    assert banco.listar_profissionais() == []


@pytest.mark.parametrize("metodo", ["obter_paciente", "obter_profissional", "obter_atendimento"])
@pytest.mark.parametrize("registro_id", [999, 0, -1, True, "1"])
def test_ids_ausentes_ou_invalidos_produzem_erro_amigavel(banco, metodo, registro_id):
    with pytest.raises(ErroDeNegocio):
        getattr(banco, metodo)(registro_id)


@pytest.mark.parametrize("payload", ["' OR 1=1 --", "'; DROP TABLE pacientes; --", "%", "_"])
def test_busca_trata_sql_injection_e_curingas_como_texto_literal(banco, payload):
    banco.cadastrar_paciente("Ana Exemplo", "123")
    assert banco.listar_pacientes(payload) == []
    literal_id = banco.cadastrar_paciente(payload, "456")
    assert [r["id"] for r in banco.listar_pacientes(payload)] == [literal_id]
    assert len(banco.listar_pacientes()) == 2


def test_apostrofo_legitimo_persiste_e_pode_ser_buscado(banco):
    paciente_id = banco.cadastrar_paciente("D'Ávila", "123")
    assert [r["id"] for r in banco.listar_pacientes("D'")] == [paciente_id]


def test_busca_sem_distinguir_maiusculas_em_nome_acentuado(banco):
    paciente_id = banco.cadastrar_paciente("Álvaro Exemplo", "123")
    assert [r["id"] for r in banco.listar_pacientes("álvaro")] == [paciente_id]


@pytest.mark.parametrize("situacao", ["agendado", "realizado", "falta"])
def test_rn1_profissional_nao_tem_dois_atendimentos_no_mesmo_horario(banco, cadastros, situacao):
    primeiro = agendar(banco, cadastros)
    mudar_situacao(banco, primeiro, situacao)
    with pytest.raises(ErroDeNegocio, match="profissional já possui"):
        agendar(banco, cadastros, paciente="p2")
    assert len(banco.listar_atendimentos(DIA)) == 1


@pytest.mark.parametrize("situacao", ["agendado", "realizado", "falta"])
def test_rn2_paciente_nao_tem_dois_atendimentos_no_mesmo_horario(banco, cadastros, situacao):
    primeiro = agendar(banco, cadastros)
    mudar_situacao(banco, primeiro, situacao)
    with pytest.raises(ErroDeNegocio, match="paciente já possui"):
        agendar(banco, cadastros, profissional="f2")
    assert len(banco.listar_atendimentos(DIA)) == 1


def test_pacientes_e_profissionais_diferentes_podem_usar_mesmo_horario(banco, cadastros):
    agendar(banco, cadastros)
    agendar(banco, cadastros, paciente="p2", profissional="f2")
    assert len(banco.listar_atendimentos(DIA)) == 2


def test_rn3_cancelamento_libera_paciente_e_profissional(banco, cadastros):
    primeiro = agendar(banco, cadastros)
    mudar_situacao(banco, primeiro, "cancelado")
    assert "08:30" in banco.horarios_livres(DIA, cadastros["p1"], cadastros["f1"])
    segundo = agendar(banco, cadastros)
    mudar_situacao(banco, segundo, "cancelado")
    terceiro = agendar(banco, cadastros)
    assert len(banco.listar_atendimentos(DIA)) == 3
    assert banco.obter_atendimento(terceiro)["situacao"] == "agendado"


@pytest.mark.parametrize("situacao", ["agendado", "realizado", "falta"])
def test_rn3_reativar_com_horario_livre(banco, cadastros, situacao):
    atendimento_id = agendar(banco, cadastros)
    mudar_situacao(banco, atendimento_id, "cancelado")
    mudar_situacao(banco, atendimento_id, situacao)
    assert banco.obter_atendimento(atendimento_id)["situacao"] == situacao
    assert "08:30" not in banco.horarios_livres(DIA, cadastros["p1"], cadastros["f1"])


@pytest.mark.parametrize("situacao", ["agendado", "realizado", "falta"])
@pytest.mark.parametrize("conflito", ["paciente", "profissional"])
def test_rn3_reativar_em_horario_ocupado_preserva_cancelamento(banco, cadastros, situacao, conflito):
    atendimento_id = agendar(banco, cadastros)
    mudar_situacao(banco, atendimento_id, "cancelado")
    agendar(banco, cadastros,
            paciente="p2" if conflito == "profissional" else "p1",
            profissional="f2" if conflito == "paciente" else "f1")
    with pytest.raises(ErroDeNegocio, match=conflito + " já possui"):
        mudar_situacao(banco, atendimento_id, situacao)
    assert banco.obter_atendimento(atendimento_id)["situacao"] == "cancelado"


@pytest.mark.parametrize("situacao", ["agendado", "realizado", "cancelado", "falta"])
def test_rn4_historico_impede_exclusao_mas_permite_edicao(banco, cadastros, situacao):
    atendimento_id = agendar(banco, cadastros)
    mudar_situacao(banco, atendimento_id, situacao)
    with pytest.raises(ErroDeNegocio, match="histórico"):
        banco.excluir_paciente(cadastros["p1"], confirmado=True)
    with pytest.raises(ErroDeNegocio, match="histórico"):
        banco.excluir_profissional(cadastros["f1"], confirmado=True)
    banco.editar_paciente(cadastros["p1"], "Ana Atualizada", "456")
    banco.editar_profissional(cadastros["f1"], "Alice Atualizada", "Clínica geral")
    assert banco.obter_paciente(cadastros["p1"])["nome"] == "Ana Atualizada"
    assert banco.obter_profissional(cadastros["f1"])["nome"] == "Alice Atualizada"
    assert banco.obter_atendimento(atendimento_id)["situacao"] == situacao


@pytest.mark.parametrize("confirmado", [False, None, 1, "sim"])
def test_rn5_cancelamento_exige_booleano_true(banco, cadastros, confirmado):
    atendimento_id = agendar(banco, cadastros)
    with pytest.raises(ErroDeNegocio, match="Confirme explicitamente"):
        banco.atualizar_atendimento(atendimento_id, situacao="cancelado", confirmado=confirmado)
    assert banco.obter_atendimento(atendimento_id)["situacao"] == "agendado"


@pytest.mark.parametrize("entidade", ["paciente", "profissional", "atendimento"])
def test_rn5_exclusao_exige_confirmacao_e_preserva_registro(banco, cadastros, entidade):
    registro_id = {"paciente": cadastros["p2"], "profissional": cadastros["f2"]}.get(entidade)
    if entidade == "atendimento":
        registro_id = agendar(banco, cadastros)
    excluir = getattr(banco, "excluir_" + entidade)
    obter = getattr(banco, "obter_" + entidade)
    with pytest.raises(ErroDeNegocio, match="Confirme explicitamente"):
        excluir(registro_id)
    assert obter(registro_id)["id"] == registro_id
    excluir(registro_id, confirmado=True)
    with pytest.raises(ErroDeNegocio, match="não encontrado"):
        obter(registro_id)


def test_rn6_modelo_do_paciente_guarda_apenas_identificacao_e_metadados(banco, cadastros):
    assert set(banco.obter_paciente(cadastros["p1"])) == {"id", "nome", "telefone", "criado_em"}
    with sqlite3.connect(banco.caminho) as con:
        colunas = {linha[1] for linha in con.execute("PRAGMA table_info(pacientes)")}
    assert colunas == {"id", "nome", "telefone", "criado_em"}


@pytest.mark.parametrize("campo,valor", [("servico", "Diagnóstico clínico"), ("observacao", "Paciente com sintomas")])
def test_rn6_texto_livre_e_rejeitado_em_servico_e_observacao(banco, cadastros, campo, valor):
    dados = {"servico": SERVICOS[0], "observacao": ""}
    dados[campo] = valor
    with pytest.raises(ErroDeNegocio):
        banco.agendar_atendimento(cadastros["p1"], cadastros["f1"], INSTANTE, **dados)
    atendimento_id = agendar(banco, cadastros)
    original = banco.obter_atendimento(atendimento_id)
    with pytest.raises(ErroDeNegocio):
        banco.atualizar_atendimento(atendimento_id, **{campo: valor})
    assert banco.obter_atendimento(atendimento_id) == original


def test_rn6_todas_as_opcoes_administrativas_podem_ser_editadas(banco, cadastros):
    atendimento_id = agendar(banco, cadastros)
    for servico in SERVICOS:
        for observacao in OBSERVACOES:
            banco.atualizar_atendimento(atendimento_id, servico=servico, observacao=observacao)
            registro = banco.obter_atendimento(atendimento_id)
            assert (registro["servico"], registro["observacao"]) == (servico, observacao)


def test_grade_util_tem_28_horarios_de_vinte_minutos():
    horarios = horarios_do_dia(DIA)
    assert len(horarios) == 28
    assert horarios[:3] == ["08:30", "08:50", "09:10"]
    assert horarios[-1] == "17:30"
    minutos = [int(h[:2]) * 60 + int(h[3:]) for h in horarios]
    assert all(segundo - primeiro == 20 for primeiro, segundo in zip(minutos, minutos[1:]))
    assert horarios_do_dia(date(2026, 9, 28)) == horarios


@pytest.mark.parametrize("dia", ["2026-10-03", "2026-10-04"])
def test_fins_de_semana_nao_tem_grade(banco, cadastros, dia):
    assert horarios_do_dia(dia) == []
    assert banco.horarios_livres(dia, cadastros["p1"], cadastros["f1"]) == []


@pytest.mark.parametrize("instante", [
    "2026-09-28 08:10", "2026-09-28 08:40", "2026-09-28 17:50",
    "2026-09-28 18:00", "2026-10-03 08:30", "2026-10-04 08:30",
    "2026-02-30 08:30", "28/09/2026 08:30", "2026-9-28 08:30",
    "2026-09-28 08:30:00", None,
])
def test_data_hora_fora_do_formato_ou_grade_e_rejeitada(banco, cadastros, instante):
    with pytest.raises(ErroDeNegocio):
        agendar(banco, cadastros, instante=instante)
    assert banco.listar_atendimentos(DIA) == []


def test_horarios_livres_consideram_ambos_e_ignoram_o_proprio_registro(banco, cadastros):
    proprio = agendar(banco, cadastros)
    agendar(banco, cadastros, profissional="f2", instante=DIA + " 08:50")
    agendar(banco, cadastros, paciente="p2", instante=DIA + " 09:10")
    livres = banco.horarios_livres(DIA, cadastros["p1"], cadastros["f1"])
    assert all(h not in livres for h in ["08:30", "08:50", "09:10"])
    assert "09:30" in livres
    editaveis = banco.horarios_livres(DIA, cadastros["p1"], cadastros["f1"], ignorar_atendimento_id=proprio)
    assert "08:30" in editaveis
    assert "08:50" not in editaveis
    assert "09:10" not in editaveis


def test_reagendar_e_filtrar_agenda_por_dia_e_profissional(banco, cadastros):
    atendimento_id = agendar(banco, cadastros)
    banco.atualizar_atendimento(atendimento_id, data_hora="2026-09-29 17:30", profissional_id=cadastros["f2"])
    assert banco.listar_atendimentos(DIA) == []
    assert banco.listar_atendimentos("2026-09-29", cadastros["f1"]) == []
    agenda = banco.listar_atendimentos("2026-09-29", cadastros["f2"])
    assert len(agenda) == 1
    assert agenda[0]["id"] == atendimento_id
    assert agenda[0]["paciente"] == "Ana Exemplo"
    assert agenda[0]["profissional"] == "Bruno Exemplo"


@pytest.mark.parametrize("conflito", ["paciente", "profissional"])
def test_reagendamento_conflitante_desfaz_todas_as_alteracoes(banco, cadastros, conflito):
    atendimento_id = agendar(banco, cadastros)
    original = banco.obter_atendimento(atendimento_id)
    agendar(banco, cadastros, instante=DIA + " 08:50",
            paciente="p2" if conflito == "profissional" else "p1",
            profissional="f2" if conflito == "paciente" else "f1")
    with pytest.raises(ErroDeNegocio, match=conflito + " já possui"):
        banco.atualizar_atendimento(atendimento_id, data_hora=DIA + " 08:50", servico="Retorno")
    assert banco.obter_atendimento(atendimento_id) == original


def test_situacao_invalida_preserva_atendimento(banco, cadastros):
    atendimento_id = agendar(banco, cadastros)
    with pytest.raises(ErroDeNegocio, match="situação válida"):
        banco.atualizar_atendimento(atendimento_id, situacao="concluido")
    assert banco.obter_atendimento(atendimento_id)["situacao"] == "agendado"


@pytest.mark.parametrize("campo", ["paciente_id", "profissional_id"])
def test_agendamento_exige_referencias_existentes(banco, cadastros, campo):
    ids = {"paciente_id": cadastros["p1"], "profissional_id": cadastros["f1"]}
    ids[campo] = 999
    with pytest.raises(ErroDeNegocio, match="não encontrado"):
        banco.agendar_atendimento(**ids, data_hora=INSTANTE, servico=SERVICOS[0])
    assert banco.listar_atendimentos(DIA) == []


def test_relatorio_periodo_inclusivo_totais_taxa_e_faltas_por_profissional(banco, cadastros):
    casos = [
        ("2026-09-25 17:30", "falta", "f1"),  # Fora do início.
        ("2026-09-28 08:30", "realizado", "f1"),
        ("2026-09-28 08:50", "realizado", "f2"),
        ("2026-09-28 09:10", "falta", "f1"),
        ("2026-09-28 09:30", "cancelado", "f2"),
        ("2026-09-29 17:30", "agendado", "f2"),  # Inclui o último dia.
        ("2026-09-30 08:30", "falta", "f2"),  # Fora do fim.
    ]
    for instante, situacao, profissional in casos:
        atendimento_id = agendar(banco, cadastros, instante=instante, profissional=profissional)
        mudar_situacao(banco, atendimento_id, situacao)
    resultado = banco.relatorio(DIA, "2026-09-29")
    assert {k: resultado[k] for k in ["total", "agendados", "realizados", "cancelados", "faltas", "taxa_faltas"]} == {
        "total": 5, "agendados": 1, "realizados": 2, "cancelados": 1, "faltas": 1, "taxa_faltas": 33.33
    }
    assert {r["profissional_id"]: r["faltas"] for r in resultado["faltas_por_profissional"]} == {
        cadastros["f1"]: 1, cadastros["f2"]: 0, cadastros["f3"]: 0
    }


def test_relatorio_vazio_tem_zero_sem_divisao_por_zero(banco):
    resultado = banco.relatorio(DIA, DIA)
    assert resultado == {
        "total": 0, "agendados": 0, "realizados": 0, "cancelados": 0,
        "faltas": 0, "taxa_faltas": 0.0, "faltas_por_profissional": []
    }


def test_relatorio_sem_encerrados_exclui_agendados_e_cancelados_do_denominador(banco, cadastros):
    agendar(banco, cadastros)
    cancelado = agendar(banco, cadastros, instante=DIA + " 08:50")
    mudar_situacao(banco, cancelado, "cancelado")
    resultado = banco.relatorio(DIA, DIA)
    assert resultado["total"] == 2
    assert resultado["taxa_faltas"] == 0.0


@pytest.mark.parametrize("inicio,fim", [("2026-09-29", DIA), ("2026-02-30", DIA), (DIA, "28/09/2026")])
def test_relatorio_rejeita_periodos_invalidos(banco, inicio, fim):
    with pytest.raises(ErroDeNegocio):
        banco.relatorio(inicio, fim)


@pytest.mark.parametrize("conflito", ["paciente", "profissional"])
def test_concorrencia_so_uma_reserva_vence(banco, cadastros, conflito):
    barreira = Barrier(2)

    def disputar(indice):
        conexao = BancoClinica(banco.caminho)
        paciente = "p1" if conflito == "paciente" or indice == 0 else "p2"
        profissional = "f1" if conflito == "profissional" or indice == 0 else "f2"
        barreira.wait(timeout=10)
        try:
            return ("sucesso", agendar(conexao, cadastros, paciente=paciente, profissional=profissional))
        except ErroDeNegocio as erro:
            return ("erro", str(erro))

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(disputar, [0, 1]))
    assert sorted(tipo for tipo, _ in resultados) == ["erro", "sucesso"]
    mensagem = next(valor for tipo, valor in resultados if tipo == "erro")
    assert conflito + " já possui" in mensagem
    assert len(banco.listar_atendimentos(DIA)) == 1


@pytest.mark.parametrize("conflito", ["paciente", "profissional"])
def test_sqlite_tambem_bloqueia_conflitos_sem_passar_pela_api(banco, cadastros, conflito):
    agendar(banco, cadastros)
    paciente_id = cadastros["p1"] if conflito == "paciente" else cadastros["p2"]
    profissional_id = cadastros["f1"] if conflito == "profissional" else cadastros["f2"]
    with sqlite3.connect(banco.caminho) as con:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO atendimentos (paciente_id, profissional_id, data_hora, servico, situacao, observacao) VALUES (?, ?, ?, ?, ?, ?)",
                (paciente_id, profissional_id, INSTANTE, SERVICOS[0], "agendado", ""),
            )
    assert len(banco.listar_atendimentos(DIA)) == 1


def test_chave_estrangeira_sqlite_preserva_historico(banco, cadastros):
    agendar(banco, cadastros)
    with sqlite3.connect(banco.caminho) as con:
        con.execute("PRAGMA foreign_keys = ON")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("DELETE FROM pacientes WHERE id = ?", (cadastros["p1"],))
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("DELETE FROM profissionais WHERE id = ?", (cadastros["f1"],))
    assert len(banco.listar_atendimentos(DIA)) == 1

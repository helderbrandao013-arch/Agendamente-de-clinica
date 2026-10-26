"""Carrega dados fictícios de demonstração, somente em um banco vazio."""

import argparse
from datetime import date, timedelta
import os
from pathlib import Path

from db import BANCO_PADRAO, BancoClinica, ErroDeNegocio


def dia_util(dia, passo=1):
    """Mantém dias úteis e avança ou recua quando a data cai no fim de semana."""
    while dia.weekday() >= 5:
        dia += timedelta(days=passo)
    return dia


def popular_banco(caminho):
    """Retorna as datas da demonstração, ou None quando já há cadastros."""
    banco = BancoClinica(caminho)
    banco.inicializar()
    if banco.listar_pacientes() or banco.listar_profissionais():
        return None

    # Nomes e telefones deliberadamente fictícios. Não há informações clínicas.
    pacientes = [
        banco.cadastrar_paciente(nome, telefone)
        for nome, telefone in (
            ("Ana Exemplo", "(00) 90000-0001"),
            ("Bruno Exemplo", "(00) 90000-0002"),
            ("Carla Exemplo", "(00) 90000-0003"),
            ("Diego Exemplo", "(00) 90000-0004"),
            ("Elisa Exemplo", "(00) 90000-0005"),
        )
    ]
    profissionais = [
        banco.cadastrar_profissional(nome, especialidade)
        for nome, especialidade in (
            ("Helena Demonstração", "Clínica geral"),
            ("Marcos Demonstração", "Odontologia"),
            ("Lúcia Demonstração", "Fisioterapia"),
        )
    ]

    hoje = date.today()
    recente = dia_util(hoje - timedelta(days=1), passo=-1)
    proximo = dia_util(hoje)

    # Índices se referem aos cadastros acima; horários obedecem à grade de 20 min.
    exemplos = (
        (recente, "08:30", 0, 0, "Consulta", "realizado", "Confirmado por telefone"),
        (recente, "08:50", 1, 0, "Retorno", "falta", "Agendado por WhatsApp"),
        (recente, "09:10", 2, 1, "Consulta", "cancelado", "Agendado por telefone"),
        (recente, "09:30", 3, 2, "Atendimento administrativo", "agendado", "Aguardando confirmação"),
        (proximo, "08:30", 0, 0, "Consulta", "agendado", "Confirmado por WhatsApp"),
        (proximo, "08:30", 2, 1, "Retorno", "agendado", "Agendado por telefone"),
        (proximo, "08:50", 4, 2, "Consulta", "agendado", "Aguardando confirmação"),
    )
    for dia, hora, paciente, profissional, servico, situacao, observacao in exemplos:
        atendimento_id = banco.agendar_atendimento(
            pacientes[paciente], profissionais[profissional],
            f"{dia.isoformat()} {hora}", servico, observacao,
        )
        if situacao != "agendado":
            # A execução deste script solicita os registros fictícios, inclusive
            # o exemplo cancelado; cancelamentos na interface exigem confirmação.
            banco.atualizar_atendimento(
                atendimento_id, situacao=situacao, confirmado=True,
            )
    return recente, proximo


def main():
    parser = argparse.ArgumentParser(
        description="Preenche um banco vazio com dados fictícios da agenda."
    )
    parser.add_argument(
        "--banco", type=Path,
        default=Path(os.environ.get("CLINICA_DB") or BANCO_PADRAO),
        help="Arquivo SQLite (padrão: CLINICA_DB ou clinica.db ao lado deste script).",
    )
    args = parser.parse_args()
    caminho = args.banco.expanduser().resolve()
    print(f"Banco: {caminho}")
    try:
        datas = popular_banco(caminho)
    except ErroDeNegocio as erro:
        print(f"Não foi possível carregar os exemplos: {erro}")
        return 1

    if datas is None:
        print("Banco já preenchido. Nenhum dado foi adicionado, apagado ou substituído.")
        return 0

    recente, proximo = datas
    print("Criados 5 pacientes, 3 profissionais e 7 atendimentos fictícios.")
    print(f"Agenda com as quatro situações: {recente:%d/%m/%Y}.")
    print(f"Próximos agendamentos: {proximo:%d/%m/%Y}.")
    print(f"Relatório de demonstração: {recente:%d/%m/%Y} a {proximo:%d/%m/%Y}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

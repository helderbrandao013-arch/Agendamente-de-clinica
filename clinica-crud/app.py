"""Interface administrativa da clínica. Execute: streamlit run app.py."""

from datetime import date, datetime, timedelta
import os

import streamlit as st

from db import BANCO_PADRAO, BancoClinica, ErroDeNegocio, OBSERVACOES, SERVICOS, SITUACOES, horarios_do_dia


PAGINAS = ("Agenda do dia", "Novo agendamento", "Pacientes", "Profissionais", "Relatórios")
ROTULOS = {"agendado": "Agendado", "realizado": "Realizado", "cancelado": "Cancelado", "falta": "Falta"}

st.set_page_config(page_title="Clínica | Agenda", page_icon="🗓️", layout="wide")
st.markdown("""
<style>
  .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
  h1 {letter-spacing: -.04em;}
  [data-testid="stMetric"] {background: #edf6f5; border-radius: 12px; padding: 16px;}
  [data-testid="stSidebar"] {border-right: 1px solid #dce9e7;}
  div.stButton > button[kind="primary"] {border-radius: 8px;}
</style>
""", unsafe_allow_html=True)


def proximo_dia_util():
    dia = date.today()
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia


def chave(prefixo):
    return f"{prefixo}_{st.session_state.get('versao', 0)}"


def salvar(operacao, mensagem):
    """Mostra erro de negócio e mantém a tela; após sucesso, recarrega os dados."""
    try:
        operacao()
    except ErroDeNegocio as erro:
        st.error(str(erro))
    else:
        st.session_state["aviso_sucesso"] = mensagem
        st.session_state["versao"] = st.session_state.get("versao", 0) + 1
        st.rerun()


def aviso_privacidade():
    st.caption("Somente dados administrativos. Não registre sintomas, diagnósticos, exames ou tratamentos.")


def escolher_registro(rotulo, registros, *, campo_extra=None, key):
    mapa = {r["id"]: r for r in registros}

    def formato(registro_id):
        registro = mapa[registro_id]
        complemento = f" · {registro[campo_extra]}" if campo_extra else ""
        return f"{registro['nome']}{complemento} · #{registro_id}"

    return st.selectbox(rotulo, list(mapa), format_func=formato, key=key)


def escolher_horario(opcoes, *, key, atual=None):
    # Se outra recepcionista ocupou a seleção anterior, não salvar outra hora
    # automaticamente: esta tentativa exige que a pessoa selecione novamente.
    anterior = st.session_state.get(key)
    perdeu_vaga = anterior is not None and anterior not in opcoes
    if perdeu_vaga:
        st.warning("O horário selecionado ficou indisponível. Escolha outro antes de salvar.")
    indice = opcoes.index(atual) if atual in opcoes and not perdeu_vaga else None
    hora = st.selectbox("Horário livre", opcoes, index=indice,
                        placeholder="Selecione um horário", key=key, disabled=not opcoes)
    return hora, perdeu_vaga


def confirmar_exclusao(rotulo, identificador, operacao):
    with st.expander(f"Excluir {rotulo}", key=chave(f"painel_excluir_{rotulo}_{identificador}")):
        st.warning("Use a exclusão apenas para corrigir um registro lançado por engano. Esta ação é definitiva.")
        confirmado = st.checkbox(
            f"Confirmo a exclusão de {identificador}.", key=chave(f"confirmar_excluir_{rotulo}_{identificador}"),
        )
        if st.button(f"Excluir {rotulo} definitivamente", disabled=not confirmado,
                     key=chave(f"excluir_{rotulo}_{identificador}")):
            salvar(lambda: operacao(confirmado=confirmado), f"{rotulo.capitalize()} excluído com sucesso.")


def pagina_pacientes(banco):
    st.title("Pacientes")
    st.write("Cadastre e mantenha os contatos usados nos agendamentos.")
    aviso_privacidade()
    with st.expander("Cadastrar paciente", expanded=True):
        with st.form(chave("novo_paciente")):
            col1, col2 = st.columns(2)
            nome = col1.text_input("Nome do paciente", key=chave("paciente_nome_novo"))
            telefone = col2.text_input("Telefone", key=chave("paciente_telefone_novo"))
            if st.form_submit_button("Cadastrar paciente", type="primary"):
                salvar(lambda: banco.cadastrar_paciente(nome, telefone), "Paciente cadastrado com sucesso.")
    busca = st.text_input("Buscar por nome ou telefone", placeholder="Digite parte do nome ou telefone")
    pacientes = banco.listar_pacientes(busca)
    st.subheader(f"Cadastros encontrados · {len(pacientes)}")
    if not pacientes:
        st.info("Nenhum paciente encontrado. Cadastre um paciente ou ajuste a busca.")
        return
    st.dataframe([{"ID": p["id"], "Nome": p["nome"], "Telefone": p["telefone"]} for p in pacientes],
                 hide_index=True, width="stretch")
    paciente_id = escolher_registro("Paciente para editar", pacientes, campo_extra="telefone", key="editar_paciente_id")
    paciente = banco.obter_paciente(paciente_id)
    with st.form(chave(f"editar_paciente_{paciente_id}")):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome", value=paciente["nome"])
        telefone = col2.text_input("Telefone atualizado", value=paciente["telefone"])
        if st.form_submit_button("Salvar paciente"):
            salvar(lambda: banco.editar_paciente(paciente_id, nome, telefone), "Cadastro do paciente atualizado.")
    st.caption("Pacientes com atendimentos registrados podem ser editados, mas não excluídos.")
    confirmar_exclusao("paciente", f"{paciente['nome']} (#{paciente_id})",
                      lambda **kw: banco.excluir_paciente(paciente_id, **kw))


def pagina_profissionais(banco):
    st.title("Profissionais")
    st.write("Mantenha os profissionais e as especialidades da clínica.")
    with st.expander("Cadastrar profissional", expanded=True):
        with st.form(chave("novo_profissional")):
            col1, col2 = st.columns(2)
            nome = col1.text_input("Nome do profissional")
            especialidade = col2.text_input("Especialidade")
            if st.form_submit_button("Cadastrar profissional", type="primary"):
                salvar(lambda: banco.cadastrar_profissional(nome, especialidade), "Profissional cadastrado com sucesso.")
    profissionais = banco.listar_profissionais()
    st.subheader(f"Profissionais cadastrados · {len(profissionais)}")
    if not profissionais:
        st.info("Cadastre um profissional para começar a agendar.")
        return
    st.dataframe([{"ID": p["id"], "Nome": p["nome"], "Especialidade": p["especialidade"]} for p in profissionais],
                 hide_index=True, width="stretch")
    profissional_id = escolher_registro("Profissional para editar", profissionais,
                                       campo_extra="especialidade", key="editar_profissional_id")
    profissional = banco.obter_profissional(profissional_id)
    with st.form(chave(f"editar_profissional_{profissional_id}")):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome", value=profissional["nome"])
        especialidade = col2.text_input("Especialidade atualizada", value=profissional["especialidade"])
        if st.form_submit_button("Salvar profissional"):
            salvar(lambda: banco.editar_profissional(profissional_id, nome, especialidade), "Cadastro do profissional atualizado.")
    st.caption("Profissionais com atendimentos registrados podem ser editados, mas não excluídos.")
    confirmar_exclusao("profissional", f"{profissional['nome']} (#{profissional_id})",
                      lambda **kw: banco.excluir_profissional(profissional_id, **kw))


def pagina_novo_agendamento(banco):
    st.title("Novo agendamento")
    st.write("Escolha os participantes e a data para consultar os horários disponíveis.")
    aviso_privacidade()
    pacientes, profissionais = banco.listar_pacientes(), banco.listar_profissionais()
    if not pacientes or not profissionais:
        st.info("Cadastre pelo menos um paciente e um profissional nas páginas correspondentes.")
        return
    col1, col2 = st.columns(2)
    with col1:
        paciente_id = escolher_registro("Paciente", pacientes, campo_extra="telefone", key=chave("novo_paciente_id"))
    with col2:
        profissional_id = escolher_registro("Profissional", profissionais, campo_extra="especialidade", key=chave("novo_profissional_id"))
    dia = st.date_input("Dia do atendimento", value=proximo_dia_util(), format="DD/MM/YYYY", key=chave("novo_dia"))
    horarios = banco.horarios_livres(dia, paciente_id, profissional_id)
    if dia.weekday() >= 5:
        st.info("A clínica atende de segunda a sexta. Selecione um dia útil.")
    elif not horarios:
        st.info("Não há horários livres para este paciente e profissional na data selecionada.")
    col1, col2 = st.columns(2)
    with col1:
        hora, perdeu_vaga = escolher_horario(horarios, key=chave(f"novo_hora_{paciente_id}_{profissional_id}_{dia}"))
        st.caption(f"{len(horarios)} horários livres · duração de 20 minutos")
    with col2:
        servico = st.selectbox("Serviço", SERVICOS, key=chave("novo_servico"))
    observacao = st.selectbox("Observação administrativa", OBSERVACOES,
                             format_func=lambda s: s or "Sem observação", key=chave("novo_observacao"))
    if st.button("Agendar atendimento", type="primary", disabled=hora is None or perdeu_vaga):
        salvar(lambda: banco.agendar_atendimento(paciente_id, profissional_id,
                                                f"{dia.isoformat()} {hora}", servico, observacao),
               f"Atendimento agendado para {dia:%d/%m/%Y} às {hora}.")


def editar_atendimento(banco, atendimento_id):
    registro = banco.obter_atendimento(atendimento_id)
    paciente = banco.obter_paciente(registro["paciente_id"])
    st.subheader("Editar atendimento")
    st.write(f"Paciente: {paciente['nome']} · Atendimento #{atendimento_id}")
    aviso_privacidade()
    base = chave(f"atendimento_{atendimento_id}")
    situacao = st.selectbox("Situação", SITUACOES, index=SITUACOES.index(registro["situacao"]),
                           format_func=ROTULOS.get, key=f"{base}_situacao")
    profissionais = banco.listar_profissionais()
    mapa = {p["id"]: p for p in profissionais}
    col1, col2 = st.columns(2)
    with col1:
        profissional_id = st.selectbox("Profissional do atendimento", list(mapa),
                                        index=list(mapa).index(registro["profissional_id"]),
                                        format_func=lambda i: f"{mapa[i]['nome']} · {mapa[i]['especialidade']} · #{i}",
                                        key=f"{base}_profissional")
    with col2:
        dia = st.date_input("Data do atendimento", value=datetime.strptime(registro["data_hora"], "%Y-%m-%d %H:%M").date(),
                            format="DD/MM/YYYY", key=f"{base}_dia")
    if situacao == "cancelado":
        horarios = horarios_do_dia(dia)
        st.caption("Um atendimento cancelado mantém seu registro e não reserva horário. A reativação exige uma vaga livre.")
    else:
        horarios = banco.horarios_livres(dia, registro["paciente_id"], profissional_id,
                                        ignorar_atendimento_id=atendimento_id)
    col1, col2 = st.columns(2)
    with col1:
        hora, perdeu_vaga = escolher_horario(horarios, atual=registro["data_hora"][11:],
                                             key=f"{base}_hora_{dia}_{profissional_id}_{situacao}")
    with col2:
        servico = st.selectbox("Serviço do atendimento", SERVICOS, index=SERVICOS.index(registro["servico"]), key=f"{base}_servico")
    observacao = st.selectbox("Observação administrativa do atendimento", OBSERVACOES,
                             index=OBSERVACOES.index(registro["observacao"]),
                             format_func=lambda s: s or "Sem observação", key=f"{base}_observacao")
    cancelar = situacao == "cancelado" and registro["situacao"] != "cancelado"
    confirmado = False
    if cancelar:
        st.warning("O cancelamento libera o horário e mantém o atendimento no relatório.")
        confirmado = st.checkbox(f"Confirmo o cancelamento do atendimento #{atendimento_id}.", key=f"{base}_confirmar_cancelamento")
    if not horarios:
        st.info("Não há horários livres. Escolha outra data ou profissional para reagendar ou reativar.")
    if st.button("Salvar alterações do atendimento", type="primary",
                 disabled=hora is None or perdeu_vaga or (cancelar and not confirmado)):
        salvar(lambda: banco.atualizar_atendimento(atendimento_id, profissional_id=profissional_id,
                                                  data_hora=f"{dia.isoformat()} {hora}", servico=servico,
                                                  situacao=situacao, observacao=observacao, confirmado=confirmado),
               "Atendimento atualizado com sucesso.")
    confirmar_exclusao("atendimento", f"atendimento #{atendimento_id} de {paciente['nome']}",
                      lambda **kw: banco.excluir_atendimento(atendimento_id, **kw))


def pagina_agenda(banco):
    st.title("Agenda do dia")
    st.write("Acompanhe os atendimentos, atualize as situações e organize os próximos horários.")
    col1, col2, col3 = st.columns([2, 3, 1])
    dia = col1.date_input("Data da agenda", value=date.today(), format="DD/MM/YYYY", key="agenda_dia")
    profissionais = {p["id"]: p for p in banco.listar_profissionais()}
    profissional_id = col2.selectbox("Filtrar por profissional", [None, *profissionais],
                                     format_func=lambda i: "Todos os profissionais" if i is None else f"{profissionais[i]['nome']} · #{i}")
    with col3:
        st.write("")
        if st.button("Atualizar agenda"):
            st.rerun()
    registros = banco.listar_atendimentos(dia, profissional_id)
    colunas = st.columns(4)
    colunas[0].metric("Total do dia", len(registros))
    colunas[1].metric("Agendados", sum(r["situacao"] == "agendado" for r in registros))
    colunas[2].metric("Realizados", sum(r["situacao"] == "realizado" for r in registros))
    colunas[3].metric("Faltas", sum(r["situacao"] == "falta" for r in registros))
    st.subheader(dia.strftime("Atendimentos · %d/%m/%Y"))
    if not registros:
        st.info("Nenhum atendimento nesta data e filtro. Use Novo agendamento para reservar um horário.")
        return
    st.dataframe([{
        "ID": r["id"], "Horário": r["data_hora"][11:], "Paciente": r["paciente"],
        "Profissional": r["profissional"], "Serviço": r["servico"],
        "Situação": ROTULOS[r["situacao"]], "Observação": r["observacao"],
    } for r in registros], hide_index=True, width="stretch")
    mapa = {r["id"]: r for r in registros}
    atendimento_id = st.selectbox("Atendimento para editar", list(mapa),
                                  format_func=lambda i: f"{mapa[i]['data_hora'][11:]} · {mapa[i]['paciente']} · {mapa[i]['profissional']} · #{i}",
                                  key=f"agenda_edicao_{dia}_{profissional_id}")
    st.divider()
    editar_atendimento(banco, atendimento_id)


def pagina_relatorios(banco):
    st.title("Relatórios")
    st.write("Veja o movimento da clínica e acompanhe as faltas no período.")
    col1, col2 = st.columns(2)
    inicio = col1.date_input("Data inicial", value=date.today().replace(day=1), format="DD/MM/YYYY")
    fim = col2.date_input("Data final", value=date.today(), format="DD/MM/YYYY")
    if inicio > fim:
        st.error("A data inicial não pode ser posterior à data final.")
        return
    relatorio = banco.relatorio(inicio, fim)
    colunas = st.columns(4)
    colunas[0].metric("Total de atendimentos", relatorio["total"])
    colunas[1].metric("Cancelados", relatorio["cancelados"])
    colunas[2].metric("Faltas", relatorio["faltas"])
    colunas[3].metric("Taxa de faltas", f"{relatorio['taxa_faltas']:.2f}%".replace(".", ","))
    st.caption("Taxa de faltas = faltas ÷ (realizados + faltas) × 100. Agendados e cancelados ficam fora do cálculo. "
               "Sem realizados ou faltas, a taxa é 0%. As duas datas estão incluídas no período.")
    st.write(f"Realizados: {relatorio['realizados']} · Ainda agendados: {relatorio['agendados']}")
    if not relatorio["total"]:
        st.info("Nenhum atendimento registrado neste período.")
    st.subheader("Faltas por profissional")
    linhas = [{"Profissional": r["profissional"], "ID": r["profissional_id"], "Faltas": r["faltas"]}
              for r in relatorio["faltas_por_profissional"]]
    if linhas:
        st.dataframe(linhas, hide_index=True, width="stretch")
        if relatorio["faltas"]:
            st.bar_chart([{"Profissional": f"{r['Profissional']} · #{r['ID']}", "Faltas": r["Faltas"]} for r in linhas],
                         x="Profissional", y="Faltas", color="#16857d")
    else:
        st.info("Cadastre profissionais para acompanhar este relatório.")


def main():
    banco = BancoClinica(os.environ.get("CLINICA_DB", str(BANCO_PADRAO)))
    try:
        banco.inicializar()
    except ErroDeNegocio as erro:
        st.error(str(erro))
        st.stop()
    with st.sidebar:
        st.markdown("## Clínica\nAgenda de atendimentos")
        st.divider()
        pagina = st.radio("Navegação", PAGINAS, label_visibility="collapsed")
        st.divider()
        st.caption("SEGUNDA A SEXTA")
        st.write("08h30 – 18h00")
        st.caption("Atendimentos de 20 minutos\n\nÚltimo início: 17h30")
        st.caption("Cadastro de pacientes: somente nome e telefone.")
    aviso = st.empty()
    if mensagem := st.session_state.pop("aviso_sucesso", None):
        aviso.success(mensagem)
    paginas = dict(zip(PAGINAS, (pagina_agenda, pagina_novo_agendamento, pagina_pacientes,
                                pagina_profissionais, pagina_relatorios)))
    try:
        paginas[pagina](banco)
    except ErroDeNegocio as erro:
        st.error(str(erro))
        st.caption("Atualize a página para recarregar os registros.")


if __name__ == "__main__":
    main()

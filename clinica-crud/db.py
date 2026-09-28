"""Persistência e regras da agenda. Este módulo não depende do Streamlit."""

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
import sqlite3


SITUACOES = ("agendado", "realizado", "cancelado", "falta")
SERVICOS = ("Consulta", "Retorno", "Atendimento administrativo")
OBSERVACOES = (
    "",
    "Agendado por telefone",
    "Agendado por WhatsApp",
    "Confirmado por telefone",
    "Confirmado por WhatsApp",
    "Aguardando confirmação",
)
DURACAO_MINUTOS = 20
ABERTURA = time(8, 30)
FECHAMENTO = time(18, 0)
BANCO_PADRAO = Path(__file__).resolve().with_name("clinica.db")


class ErroDeNegocio(Exception):
    """Mensagem que pode ser apresentada diretamente ao usuário."""


def _texto(valor, campo):
    if not isinstance(valor, str) or not valor.strip():
        raise ErroDeNegocio(f"Informe {campo}.")
    return valor.strip()


def _id(valor):
    if type(valor) is not int or valor <= 0:
        raise ErroDeNegocio("Selecione um registro válido.")
    return valor


def _data(valor):
    if isinstance(valor, datetime):
        raise ErroDeNegocio("Informe uma data no formato AAAA-MM-DD.")
    if isinstance(valor, date):
        return valor
    try:
        resultado = date.fromisoformat(valor)
        if resultado.isoformat() != valor:
            raise ValueError
        return resultado
    except (TypeError, ValueError):
        raise ErroDeNegocio("Informe uma data válida no formato AAAA-MM-DD.") from None


def horarios_do_dia(dia):
    """Grade de segunda a sexta; cada atendimento termina até as 18h."""
    dia = _data(dia)
    if dia.weekday() >= 5:
        return []
    atual = datetime.combine(dia, ABERTURA)
    limite = datetime.combine(dia, FECHAMENTO)
    passo = timedelta(minutes=DURACAO_MINUTOS)
    horarios = []
    while atual + passo <= limite:
        horarios.append(atual.strftime("%H:%M"))
        atual += passo
    return horarios


def _data_hora(valor):
    try:
        resultado = datetime.strptime(valor, "%Y-%m-%d %H:%M")
        if resultado.strftime("%Y-%m-%d %H:%M") != valor:
            raise ValueError
    except (TypeError, ValueError):
        raise ErroDeNegocio("Informe data e hora no formato AAAA-MM-DD HH:MM.") from None
    if resultado.strftime("%H:%M") not in horarios_do_dia(resultado.date()):
        raise ErroDeNegocio(
            "Escolha um horário de segunda a sexta, de 08:30 a 17:30, "
            "em intervalos de 20 minutos."
        )
    return valor


def _administrativo(servico, observacao):
    if servico not in SERVICOS:
        raise ErroDeNegocio("Escolha um serviço da lista. Não registre informações clínicas.")
    if observacao not in OBSERVACOES:
        raise ErroDeNegocio("Escolha uma observação administrativa da lista.")


def _confirmacao(confirmado):
    if confirmado is not True:
        raise ErroDeNegocio("Confirme explicitamente a operação antes de continuar.")


class BancoClinica:
    """Uma conexão curta por operação, com escritas atômicas e chaves estrangeiras."""

    def __init__(self, caminho=BANCO_PADRAO):
        # Banco em arquivo permite múltiplas conexões da interface e dos testes.
        self.caminho = str(caminho)
        if self.caminho == ":memory:":
            raise ErroDeNegocio("Use um arquivo SQLite; nos testes, use um arquivo temporário.")

    @contextmanager
    def _conexao(self, escrita=False):
        con = None
        try:
            con = sqlite3.connect(self.caminho, timeout=10, isolation_level=None)
            con.row_factory = sqlite3.Row
            con.create_function("casefold", 1, str.casefold, deterministic=True)
            con.execute("PRAGMA foreign_keys = ON")
            con.execute("BEGIN IMMEDIATE" if escrita else "BEGIN")
            yield con
            con.commit()
        except sqlite3.IntegrityError as erro:
            if con is not None:
                con.rollback()
            mensagem = str(erro)
            if "atendimentos.profissional_id, atendimentos.data_hora" in mensagem:
                raise ErroDeNegocio("O profissional já possui atendimento nesse horário.") from None
            if "atendimentos.paciente_id, atendimentos.data_hora" in mensagem:
                raise ErroDeNegocio("O paciente já possui atendimento nesse horário.") from None
            raise ErroDeNegocio("Operação inválida: confira os dados e os registros vinculados.") from None
        except sqlite3.OperationalError:
            if con is not None:
                con.rollback()
            raise ErroDeNegocio("Não foi possível acessar o banco. Confira o arquivo e tente novamente.") from None
        except Exception:
            if con is not None:
                con.rollback()
            raise
        finally:
            if con is not None:
                con.close()

    def inicializar(self):
        # DDL é fixo. Valores recebidos nas consultas abaixo usam sempre parâmetros ?.
        comandos = (
            """CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL CHECK(length(trim(nome)) > 0),
                telefone TEXT NOT NULL CHECK(length(trim(telefone)) > 0),
                criado_em TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS profissionais (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL CHECK(length(trim(nome)) > 0),
                especialidade TEXT NOT NULL CHECK(length(trim(especialidade)) > 0)
            )""",
            """CREATE TABLE IF NOT EXISTS atendimentos (
                id INTEGER PRIMARY KEY,
                paciente_id INTEGER NOT NULL REFERENCES pacientes(id) ON DELETE RESTRICT,
                profissional_id INTEGER NOT NULL REFERENCES profissionais(id) ON DELETE RESTRICT,
                data_hora TEXT NOT NULL,
                servico TEXT NOT NULL CHECK(servico IN
                    ('Consulta', 'Retorno', 'Atendimento administrativo')),
                situacao TEXT NOT NULL CHECK(situacao IN
                    ('agendado', 'realizado', 'cancelado', 'falta')),
                observacao TEXT NOT NULL DEFAULT '' CHECK(observacao IN
                    ('', 'Agendado por telefone', 'Agendado por WhatsApp',
                    'Confirmado por telefone', 'Confirmado por WhatsApp', 'Aguardando confirmação'))
            )""",
            """CREATE UNIQUE INDEX IF NOT EXISTS horario_profissional_ativo
                ON atendimentos(profissional_id, data_hora) WHERE situacao <> 'cancelado'""",
            """CREATE UNIQUE INDEX IF NOT EXISTS horario_paciente_ativo
                ON atendimentos(paciente_id, data_hora) WHERE situacao <> 'cancelado'""",
            "CREATE INDEX IF NOT EXISTS atendimentos_por_data ON atendimentos(data_hora)",
        )
        with self._conexao(escrita=True) as con:
            for comando in comandos:
                con.execute(comando)

    @staticmethod
    def _paciente(con, paciente_id):
        registro = con.execute("SELECT * FROM pacientes WHERE id = ?", (_id(paciente_id),)).fetchone()
        if registro is None:
            raise ErroDeNegocio("Paciente não encontrado. Atualize a página.")
        return dict(registro)

    @staticmethod
    def _profissional(con, profissional_id):
        registro = con.execute("SELECT * FROM profissionais WHERE id = ?", (_id(profissional_id),)).fetchone()
        if registro is None:
            raise ErroDeNegocio("Profissional não encontrado. Atualize a página.")
        return dict(registro)

    @staticmethod
    def _atendimento(con, atendimento_id):
        registro = con.execute("SELECT * FROM atendimentos WHERE id = ?", (_id(atendimento_id),)).fetchone()
        if registro is None:
            raise ErroDeNegocio("Atendimento não encontrado. Atualize a página.")
        return dict(registro)

    def cadastrar_paciente(self, nome, telefone):
        nome, telefone = _texto(nome, "o nome do paciente"), _texto(telefone, "o telefone")
        with self._conexao(escrita=True) as con:
            return con.execute(
                "INSERT INTO pacientes (nome, telefone, criado_em) VALUES (?, ?, ?)",
                (nome, telefone, datetime.now().isoformat(timespec="seconds")),
            ).lastrowid

    def listar_pacientes(self, busca=""):
        if not isinstance(busca, str):
            raise ErroDeNegocio("Informe um texto para buscar.")
        with self._conexao() as con:
            # instr trata %, _ e apóstrofos como texto literal, sem interpolar SQL.
            return [dict(r) for r in con.execute(
                """SELECT * FROM pacientes WHERE instr(casefold(nome), casefold(?)) > 0
                   OR instr(telefone, ?) > 0 ORDER BY nome COLLATE NOCASE, id""",
                (busca.strip(), busca.strip()),
            )]

    def obter_paciente(self, paciente_id):
        with self._conexao() as con:
            return self._paciente(con, paciente_id)

    def editar_paciente(self, paciente_id, nome, telefone):
        nome, telefone = _texto(nome, "o nome do paciente"), _texto(telefone, "o telefone")
        with self._conexao(escrita=True) as con:
            self._paciente(con, paciente_id)
            con.execute("UPDATE pacientes SET nome = ?, telefone = ? WHERE id = ?", (nome, telefone, paciente_id))

    def excluir_paciente(self, paciente_id, *, confirmado=False):
        _confirmacao(confirmado)
        with self._conexao(escrita=True) as con:
            self._paciente(con, paciente_id)
            if con.execute("SELECT 1 FROM atendimentos WHERE paciente_id = ? LIMIT 1", (paciente_id,)).fetchone():
                raise ErroDeNegocio("Paciente com histórico de atendimentos não pode ser excluído. Edite o cadastro.")
            con.execute("DELETE FROM pacientes WHERE id = ?", (paciente_id,))

    def cadastrar_profissional(self, nome, especialidade):
        nome, especialidade = _texto(nome, "o nome do profissional"), _texto(especialidade, "a especialidade")
        with self._conexao(escrita=True) as con:
            return con.execute("INSERT INTO profissionais (nome, especialidade) VALUES (?, ?)", (nome, especialidade)).lastrowid

    def listar_profissionais(self):
        with self._conexao() as con:
            return [dict(r) for r in con.execute("SELECT * FROM profissionais ORDER BY nome COLLATE NOCASE, id")]

    def obter_profissional(self, profissional_id):
        with self._conexao() as con:
            return self._profissional(con, profissional_id)

    def editar_profissional(self, profissional_id, nome, especialidade):
        nome, especialidade = _texto(nome, "o nome do profissional"), _texto(especialidade, "a especialidade")
        with self._conexao(escrita=True) as con:
            self._profissional(con, profissional_id)
            con.execute("UPDATE profissionais SET nome = ?, especialidade = ? WHERE id = ?", (nome, especialidade, profissional_id))

    def excluir_profissional(self, profissional_id, *, confirmado=False):
        _confirmacao(confirmado)
        with self._conexao(escrita=True) as con:
            self._profissional(con, profissional_id)
            if con.execute("SELECT 1 FROM atendimentos WHERE profissional_id = ? LIMIT 1", (profissional_id,)).fetchone():
                raise ErroDeNegocio("Profissional com histórico de atendimentos não pode ser excluído. Edite o cadastro.")
            con.execute("DELETE FROM profissionais WHERE id = ?", (profissional_id,))

    def _validar_atendimento(self, con, registro, ignorar_id=None):
        self._paciente(con, registro["paciente_id"])
        self._profissional(con, registro["profissional_id"])
        _data_hora(registro["data_hora"])
        _administrativo(registro["servico"], registro["observacao"])
        if registro["situacao"] not in SITUACOES:
            raise ErroDeNegocio("Escolha uma situação válida.")
        if registro["situacao"] == "cancelado":
            return
        conflitos = con.execute(
            """SELECT paciente_id, profissional_id FROM atendimentos
               WHERE data_hora = ? AND situacao <> ? AND (? IS NULL OR id <> ?)
               AND (paciente_id = ? OR profissional_id = ?)""",
            (registro["data_hora"], "cancelado", ignorar_id, ignorar_id,
             registro["paciente_id"], registro["profissional_id"]),
        ).fetchall()
        if any(r["profissional_id"] == registro["profissional_id"] for r in conflitos):
            raise ErroDeNegocio("O profissional já possui atendimento nesse horário.")
        if conflitos:
            raise ErroDeNegocio("O paciente já possui atendimento nesse horário.")

    def agendar_atendimento(self, paciente_id, profissional_id, data_hora, servico, observacao=""):
        registro = dict(paciente_id=paciente_id, profissional_id=profissional_id,
                        data_hora=data_hora, servico=servico, situacao="agendado", observacao=observacao)
        with self._conexao(escrita=True) as con:
            self._validar_atendimento(con, registro)
            return con.execute(
                """INSERT INTO atendimentos
                   (paciente_id, profissional_id, data_hora, servico, situacao, observacao)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (paciente_id, profissional_id, data_hora, servico, "agendado", observacao),
            ).lastrowid

    def obter_atendimento(self, atendimento_id):
        with self._conexao() as con:
            return self._atendimento(con, atendimento_id)

    def listar_atendimentos(self, dia, profissional_id=None):
        dia = _data(dia).isoformat()
        with self._conexao() as con:
            if profissional_id is not None:
                self._profissional(con, profissional_id)
            return [dict(r) for r in con.execute(
                """SELECT a.*, p.nome AS paciente, p.telefone, pr.nome AS profissional,
                          pr.especialidade FROM atendimentos a
                   JOIN pacientes p ON p.id = a.paciente_id
                   JOIN profissionais pr ON pr.id = a.profissional_id
                   WHERE a.data_hora >= ? AND a.data_hora <= ?
                     AND (? IS NULL OR a.profissional_id = ?)
                   ORDER BY a.data_hora, pr.nome, a.id""",
                (dia + " 00:00", dia + " 23:59", profissional_id, profissional_id),
            )]

    def horarios_livres(self, dia, paciente_id, profissional_id, *, ignorar_atendimento_id=None):
        dia = _data(dia)
        with self._conexao() as con:
            self._paciente(con, paciente_id)
            self._profissional(con, profissional_id)
            if ignorar_atendimento_id is not None:
                self._atendimento(con, ignorar_atendimento_id)
            ocupados = {r["data_hora"][11:] for r in con.execute(
                """SELECT data_hora FROM atendimentos
                   WHERE data_hora >= ? AND data_hora <= ? AND situacao <> ?
                   AND (paciente_id = ? OR profissional_id = ?)
                   AND (? IS NULL OR id <> ?)""",
                (dia.isoformat() + " 00:00", dia.isoformat() + " 23:59", "cancelado",
                 paciente_id, profissional_id, ignorar_atendimento_id, ignorar_atendimento_id),
            )}
            return [hora for hora in horarios_do_dia(dia) if hora not in ocupados]

    def atualizar_atendimento(self, atendimento_id, *, data_hora=None, profissional_id=None,
                             servico=None, situacao=None, observacao=None, confirmado=False):
        """Altera os campos juntos: conflito ou erro desfaz toda a operação."""
        with self._conexao(escrita=True) as con:
            anterior = self._atendimento(con, atendimento_id)
            novo = dict(anterior)
            alteracoes = dict(data_hora=data_hora, profissional_id=profissional_id,
                             servico=servico, situacao=situacao, observacao=observacao)
            novo.update({campo: valor for campo, valor in alteracoes.items() if valor is not None})
            if anterior["situacao"] != "cancelado" and novo["situacao"] == "cancelado":
                _confirmacao(confirmado)
            self._validar_atendimento(con, novo, ignorar_id=atendimento_id)
            con.execute(
                """UPDATE atendimentos SET profissional_id = ?, data_hora = ?, servico = ?,
                   situacao = ?, observacao = ? WHERE id = ?""",
                (novo["profissional_id"], novo["data_hora"], novo["servico"],
                 novo["situacao"], novo["observacao"], atendimento_id),
            )

    def excluir_atendimento(self, atendimento_id, *, confirmado=False):
        _confirmacao(confirmado)
        with self._conexao(escrita=True) as con:
            self._atendimento(con, atendimento_id)
            con.execute("DELETE FROM atendimentos WHERE id = ?", (atendimento_id,))

    def relatorio(self, inicio, fim):
        inicio, fim = _data(inicio), _data(fim)
        if inicio > fim:
            raise ErroDeNegocio("A data inicial não pode ser posterior à data final.")
        limites = (inicio.isoformat() + " 00:00", fim.isoformat() + " 23:59")
        with self._conexao() as con:
            contagens = {s: 0 for s in SITUACOES}
            for r in con.execute(
                """SELECT situacao, COUNT(*) AS quantidade FROM atendimentos
                   WHERE data_hora >= ? AND data_hora <= ? GROUP BY situacao""", limites,
            ):
                contagens[r["situacao"]] = r["quantidade"]
            por_profissional = [dict(r) for r in con.execute(
                """SELECT pr.id AS profissional_id, pr.nome AS profissional,
                          COUNT(a.id) AS faltas FROM profissionais pr
                   LEFT JOIN atendimentos a ON a.profissional_id = pr.id
                     AND a.situacao = ? AND a.data_hora >= ? AND a.data_hora <= ?
                   GROUP BY pr.id, pr.nome ORDER BY faltas DESC, pr.nome, pr.id""",
                ("falta", *limites),
            )]
        encerrados = contagens["realizado"] + contagens["falta"]
        return {
            "total": sum(contagens.values()),
            "agendados": contagens["agendado"],
            "realizados": contagens["realizado"],
            "cancelados": contagens["cancelado"],
            "faltas": contagens["falta"],
            "taxa_faltas": round(100 * contagens["falta"] / encerrados, 2) if encerrados else 0.0,
            "faltas_por_profissional": por_profissional,
        }

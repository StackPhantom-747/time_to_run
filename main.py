import csv
import io
import inspect
import re
import flet as ft
from functools import wraps
from datetime import date, datetime
from config import APP_TITLE
from db import DatabaseConnectionError, query, execute
from permissions import pode as usuario_pode
from reports import gerar_csv_classificacao, gerar_pdf_classificacao
from services import (
    autenticar_utilizador,
    calcular_classificacoes,
    obter_dados_area_aluno,
)

S = {"user": None, "prova_id": None}

VERDE = "#16834A"
VERDE_ESCURO = "#11663A"
VERDE_CLARO = "#E8F5EC"
VERMELHO = "#C93C3C"
FUNDO = "#F3F6F4"
TEXTO = "#24332A"


CICLOS_ANOS = {
    "2": ("5", "6"),
    "3": ("7", "8", "9"),
    "secundario": ("10", "11", "12"),
}
CICLOS_NOMES = {
    "2": "2.º ciclo",
    "3": "3.º ciclo",
    "secundario": "Secundário",
}


def _identificar_turma(codigo, nome):
    padrao = re.compile(
        r"(?<!\d)0?(5|6|7|8|9|10|11|12)\s*(?:\.?\s*(?:º|°|o))?\s*([A-Z])"
        r"(?=$|[\s\-/])",
        re.IGNORECASE,
    )
    for texto in (codigo or "", nome or ""):
        correspondencia = padrao.search(texto)
        if correspondencia:
            return correspondencia.group(1), correspondencia.group(2).upper()
    return None, None


def _avisar_sem_base_de_dados():
    page = S.get("_page")
    if page is None:
        return False
    page.show_dialog(ft.SnackBar(
        content="Não está conectado à base de dados. Verifique a ligação e tente novamente.",
        bgcolor=VERMELHO,
        duration=6000,
    ))
    return True


def _mostrar_mensagem(page, texto, sucesso=True):
    page.show_dialog(ft.SnackBar(
        content=texto,
        bgcolor=VERDE if sucesso else VERMELHO,
        duration=4000,
    ))


def _tratar_falha_de_ligacao(callback):
    if inspect.iscoroutinefunction(callback):
        @wraps(callback)
        async def chamada_assincrona(*args, **kwargs):
            try:
                return await callback(*args, **kwargs)
            except DatabaseConnectionError:
                if not _avisar_sem_base_de_dados():
                    raise
        return chamada_assincrona

    @wraps(callback)
    def chamada(*args, **kwargs):
        try:
            return callback(*args, **kwargs)
        except DatabaseConnectionError:
            if not _avisar_sem_base_de_dados():
                raise
    return chamada


def login_view(page: ft.Page, on_ok):
    erro = ft.Text("", color=VERMELHO, text_align=ft.TextAlign.CENTER)
    user = ft.TextField(label="Utilizador", width=340, autofocus=True)
    pwd = ft.TextField(label="Palavra-passe", password=True, can_reveal_password=True, width=340)

    @_tratar_falha_de_ligacao
    def entrar(e):
        resultado, utilizador = autenticar_utilizador(
            (user.value or "").strip(),
            pwd.value or "",
        )
        if resultado == "invalid":
            erro.value = "Credenciais inválidas."
            page.update(); return
        if resultado == "inactive":
            erro.value = "Conta desativada."
            page.update(); return
        S["user"] = utilizador
        on_ok()

    pwd.on_submit = entrar

    page.clean()
    page.bgcolor = FUNDO
    page.add(ft.Column([ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(ft.Icons.FLAG, color=ft.Colors.WHITE, size=30),
                    width=64, height=64, alignment=ft.Alignment(0, 0),
                    bgcolor=VERDE, border_radius=20,
                ),
                ft.Text(APP_TITLE, size=25, weight=ft.FontWeight.BOLD,
                        color=TEXTO, text_align=ft.TextAlign.CENTER),
                ft.Text("Gestão do Corta-Mato Escolar", size=14,
                        color=ft.Colors.GREY_700),
                ft.Container(height=8),
                user, pwd, erro,
                ft.Button(
                    "Iniciar sessão", icon=ft.Icons.LOGIN, on_click=entrar,
                    width=340, height=48,
                    style=ft.ButtonStyle(
                        bgcolor=VERDE, color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
        ),
        width=440,
        padding=36,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, "#E2E9E4"),
        border_radius=22,
    )],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    ))

def home_view(page: ft.Page, on_logout):
    if "Aluno" in S["user"]["perfis"]:
        area_aluno_view(page, on_logout)
        return

    provas = query("SELECT id, nome, ano, estado FROM provas ORDER BY ano DESC, id DESC")
    if not S["prova_id"] and provas:
        S["prova_id"] = provas[0]["id"]

    prova_dd = ft.Dropdown(
        label="Prova",
        width=420,
        options=[ft.dropdown.Option(str(p["id"]), f"{p['nome']} ({p['ano']})") for p in provas],
        value=str(S["prova_id"]) if S["prova_id"] else None,
    )

    @_tratar_falha_de_ligacao
    def escolher_prova(e):
        S["prova_id"] = int(prova_dd.value)
        corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
        page.update()

    prova_dd.on_change = escolher_prova

    corpo = ft.Container(expand=True)

    @_tratar_falha_de_ligacao
    def atualizar_provas():
        provas_atualizadas = query(
            "SELECT id, nome, ano, estado FROM provas ORDER BY ano DESC, id DESC"
        )
        ids_provas = {p["id"] for p in provas_atualizadas}
        selecao_alterada = S["prova_id"] not in ids_provas
        if selecao_alterada:
            S["prova_id"] = provas_atualizadas[0]["id"] if provas_atualizadas else None
        prova_dd.options = [
            ft.dropdown.Option(str(p["id"]), f"{p['nome']} ({p['ano']})")
            for p in provas_atualizadas
        ]
        prova_dd.value = str(S["prova_id"]) if S["prova_id"] else None
        if selecao_alterada:
            corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
        page.update()

    @_tratar_falha_de_ligacao
    def escolher_secao(e):
        S["_secao"] = e.control.data
        corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
        painel_menu.content = criar_menu()
        page.update()

    S.setdefault("_secao", "inscricoes")

    def item(icon, label, secao, modulo):
        ativo = usuario_pode(S["user"], modulo)
        selecionado = S["_secao"] == secao
        cor = VERDE_ESCURO if selecionado else TEXTO
        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, color=VERDE if selecionado else ft.Colors.GREY_600,
                            size=20),
                    ft.Text(label, color=cor, weight=ft.FontWeight.W_600
                            if selecionado else ft.FontWeight.NORMAL),
                ],
                spacing=14,
            ),
            data=secao,
            on_click=escolher_secao if ativo else None,
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            border_radius=12,
            bgcolor=VERDE_CLARO if selecionado else None,
            opacity=1 if ativo else 0.42,
        )

    def criar_menu():
        return ft.Column([
            ft.Container(
                content=ft.Row([
                    ft.CircleAvatar(
                        content=ft.Text(S["user"]["nome"][:1].upper(),
                                        color=ft.Colors.WHITE,
                                        weight=ft.FontWeight.BOLD),
                        bgcolor=VERDE,
                    ),
                    ft.Column([
                        ft.Text(S["user"]["nome"], weight=ft.FontWeight.BOLD,
                                color=TEXTO),
                        ft.Text(", ".join(S["user"]["perfis"]), size=11,
                                color=ft.Colors.GREY_700),
                    ], spacing=2, expand=True),
                ], spacing=12),
                padding=ft.Padding.only(left=8, right=8, top=8, bottom=16),
            ),
            ft.Divider(),
            ft.Text("MENU", size=11, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.GREY_600),
            item(ft.Icons.DASHBOARD, "Resumo", "resumo", "resumo"),
            item(ft.Icons.SETTINGS, "Configurações", "config", "config"),
            item(ft.Icons.EDIT_NOTE, "Inscrições", "inscricoes", "inscricoes"),
            item(ft.Icons.SCHOOL, "Alunos", "alunos", "alunos"),
            item(ft.Icons.PLAY_ARROW, "Partida", "partida", "partida"),
            item(ft.Icons.FLAG, "Meta", "meta", "meta"),
            item(ft.Icons.LEADERBOARD, "Classificações", "classificacoes",
                 "classificacoes"),
            item(ft.Icons.DESCRIPTION, "Relatórios", "relatorios", "relatorios"),
            item(ft.Icons.PEOPLE, "Utilizadores", "responsaveis", "responsaveis"),
            ft.Container(expand=True),
            ft.Divider(),
            ft.TextButton(
                "Terminar sessão", icon=ft.Icons.LOGOUT,
                on_click=lambda e: on_logout(),
                style=ft.ButtonStyle(color=VERMELHO),
            ),
        ], spacing=5, expand=True)

    corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
    painel_menu = ft.Container(
        content=criar_menu(),
        width=270,
        padding=16,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, "#E2E9E4"),
        border_radius=18,
    )

    page.clean()
    page.bgcolor = FUNDO
    page.add(ft.Column([
        ft.Container(
            content=ft.Row([
                ft.Row([
                    ft.Container(
                        content=ft.Icon(ft.Icons.FLAG, color=ft.Colors.WHITE, size=22),
                        width=42, height=42, alignment=ft.Alignment(0, 0),
                        bgcolor=VERDE, border_radius=13,
                    ),
                    ft.Column([
                        ft.Text(APP_TITLE, size=17, weight=ft.FontWeight.BOLD,
                                color=TEXTO),
                        ft.Text("Organização e resultados", size=11,
                                color=ft.Colors.GREY_700),
                    ], spacing=1),
                ], spacing=12),
                ft.Container(expand=True),
                ft.Container(content=prova_dd, width=390),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=22, vertical=12),
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#E2E9E4"),
            border_radius=18,
        ),
        ft.Row([
            painel_menu,
            ft.Container(
                content=corpo,
                padding=24,
                bgcolor=ft.Colors.WHITE,
                border=ft.Border.all(1, "#E2E9E4"),
                border_radius=18,
                expand=True,
            ),
        ], expand=True, spacing=16, vertical_alignment=ft.CrossAxisAlignment.STRETCH),
    ], expand=True, spacing=16))


@_tratar_falha_de_ligacao
def area_aluno_view(page, on_logout):
    aluno, inscricoes = obter_dados_area_aluno(S["user"]["username"])

    detalhes_aluno = []
    if aluno:
        detalhes_aluno.extend([
            ft.Text("Os meus dados", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(aluno["nome"], size=22, weight=ft.FontWeight.BOLD, color=TEXTO),
            ft.Text(
                f"N.º {aluno['numero_aluno']} · Turma {aluno['turma_codigo']} — "
                f"{aluno['turma_nome']} · Ano letivo {aluno['ano_letivo']}",
                color=ft.Colors.GREY_700,
            ),
            ft.Divider(),
            ft.Text("As minhas provas", size=18, weight=ft.FontWeight.BOLD),
        ])

        if not inscricoes:
            detalhes_aluno.append(ft.Text("Ainda não existem inscrições associadas à sua conta."))

        for inscricao in inscricoes:
            resultados = []
            if inscricao["posicao_geral"] is not None:
                resultados.append(
                    f"Classificação geral: {inscricao['posicao_geral']}"
                )
                if inscricao["posicao_escalao"] is not None:
                    resultados.append(
                        f"Escalão: {inscricao['posicao_escalao']}"
                    )
                if inscricao["posicao_genero"] is not None:
                    resultados.append(
                        f"Género: {inscricao['posicao_genero']}"
                    )
                if inscricao["apurado"]:
                    resultados.append("Apurado para a fase seguinte")
            else:
                resultados.append("Classificação ainda não publicada.")

            if inscricao["ordem_chegada"] is not None:
                resultados.append(f"Ordem de chegada: {inscricao['ordem_chegada']}")

            detalhes_aluno.append(ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"{inscricao['prova_nome']} ({inscricao['ano']})",
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        f"Estado: {inscricao['estado']} · Dorsal: "
                        f"{inscricao['dorsal'] or 'Por atribuir'} · "
                        f"Escalão: {inscricao['escalao'] or 'Por definir'}"
                    ),
                    ft.Text(
                        f"{inscricao['data'] or 'Data não definida'} · "
                        f"{inscricao['local'] or 'Local não definido'}",
                        color=ft.Colors.GREY_700,
                    ),
                    ft.Text(" · ".join(resultados)),
                ], spacing=6),
                padding=16,
                border=ft.Border.all(1, "#E2E9E4"),
                border_radius=14,
                bgcolor=ft.Colors.WHITE,
            ))
    else:
        detalhes_aluno = [
            ft.Text("Conta de aluno", size=18, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Não foi encontrado um aluno com este número de utilizador. "
                "Peça à secretaria para verificar a conta.",
                color=VERMELHO,
            ),
        ]

    page.clean()
    page.bgcolor = FUNDO
    page.add(ft.Column([
        ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SCHOOL, color=VERDE, size=28),
                ft.Column([
                    ft.Text(APP_TITLE, size=17, weight=ft.FontWeight.BOLD, color=TEXTO),
                    ft.Text("Área do aluno", size=12, color=ft.Colors.GREY_700),
                ], spacing=2),
                ft.Container(expand=True),
                ft.TextButton(
                    "Terminar sessão", icon=ft.Icons.LOGOUT,
                    on_click=lambda e: on_logout(),
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=22, vertical=12),
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#E2E9E4"),
            border_radius=18,
        ),
        ft.Container(
            content=ft.Column(detalhes_aluno, spacing=12, scroll=ft.ScrollMode.AUTO),
            padding=24,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#E2E9E4"),
            border_radius=18,
            expand=True,
        ),
    ], expand=True, spacing=16))


def _corpo_atual(page, on_logout, on_prova_apagada=None):
    secao = S.get("_secao", "config")
    if secao == "resumo":
        return resumo_view(page)
    if secao == "config":
        return config_view(page, on_prova_apagada)
    if secao == "inscricoes":  return inscricoes_view(page)
    if secao == "alunos":      return alunos_view(page)
    if secao == "partida":     return partida_view(page)
    if secao == "meta":        return meta_view(page)
    if secao == "classificacoes": return classificacoes_view(page)
    if secao == "relatorios":  return relatorios_view(page)
    if secao == "responsaveis": return responsaveis_view(page)
    return ft.Text("?")


def resumo_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Column([
            ft.Text("Resumo", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Cria primeiro uma prova em Configurações.", color=ft.Colors.GREY_700),
        ])

    prova = query(
        "SELECT nome, ano, data, local, estado FROM provas WHERE id=%s",
        (pid,), one=True,
    )
    inscritos = query(
        "SELECT COUNT(*) AS total FROM inscricoes WHERE prova_id=%s",
        (pid,), one=True,
    )["total"]
    participantes = query(
        "SELECT COUNT(*) AS total FROM inscricoes "
        "WHERE prova_id=%s AND estado='Participante'",
        (pid,), one=True,
    )["total"]
    chegadas = query(
        "SELECT COUNT(*) AS total FROM chegadas WHERE prova_id=%s",
        (pid,), one=True,
    )["total"]
    ocorrencias = query(
        "SELECT COUNT(*) AS total FROM ocorrencias WHERE prova_id=%s",
        (pid,), one=True,
    )["total"]

    def cartao(titulo, valor, icone, cor=VERDE):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(icone, color=cor),
                    ft.Text(titulo, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700),
                ], spacing=8),
                ft.Text(str(valor), size=28, weight=ft.FontWeight.BOLD, color=TEXTO),
            ], spacing=8),
            width=210,
            padding=18,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, "#DCE6DF"),
            border_radius=14,
        )

    detalhes = []
    if prova:
        detalhes = [
            ft.Text(prova["nome"], size=18, weight=ft.FontWeight.BOLD),
            ft.Text(
                f"{prova['ano']} · {prova['data'] or 'Sem data'} · "
                f"{prova['local'] or 'Local não definido'} · {prova['estado']}",
                color=ft.Colors.GREY_700,
            ),
        ]

    return ft.Column([
        ft.Text("Resumo", size=20, weight=ft.FontWeight.BOLD),
        ft.Column(detalhes, spacing=2),
        ft.Row([
            cartao("Inscritos", inscritos, ft.Icons.PEOPLE),
            cartao("Participantes", participantes, ft.Icons.DIRECTIONS_RUN),
            cartao("Chegadas", chegadas, ft.Icons.FLAG),
            cartao("Ocorrências", ocorrencias, ft.Icons.REPORT_PROBLEM, VERMELHO),
        ], wrap=True, spacing=12, run_spacing=12),
    ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)


def config_view(page, on_prova_apagada=None):
    lista = ft.Column()
    nome = ft.TextField(label="Nome da prova", width=280)
    ano = ft.TextField(label="Ano", width=100, value=str(date.today().year))
    local = ft.TextField(label="Local", width=220)
    data_ = ft.TextField(label="Data (AAAA-MM-DD)", width=160)
    estado = ft.Dropdown(label="Estado", width=140, value="Planeada",
                         options=[ft.dropdown.Option(x) for x in ("Planeada", "Em curso", "Terminada")])

    def carregar():
        lista.controls.clear()
        for p in query("SELECT * FROM provas ORDER BY ano DESC, id DESC"):
            lista.controls.append(ft.ListTile(
                title=ft.Text(f"{p['nome']} — {p['ano']}"),
                subtitle=ft.Text(f"{p['data'] or '-'} · {p['local'] or '-'} · {p['estado']}"),
                trailing=ft.Row([
                    ft.IconButton(ft.Icons.EDIT, data=p["id"], on_click=editar,
                                  tooltip="Editar prova"),
                    ft.IconButton(ft.Icons.DELETE, data=p["id"],
                                  on_click=confirmar_apagamento,
                                  icon_color=VERMELHO, tooltip="Apagar prova"),
                ], tight=True, spacing=0),
            ))
        page.update()

    @_tratar_falha_de_ligacao
    def confirmar_apagar_todas(page_event=None):
        quantidade = query("SELECT COUNT(*) AS total FROM provas", one=True)["total"]

        if quantidade == 0:
            page.show_dialog(ft.SnackBar(
                content="Não existem provas para apagar.",
                duration=4000,
            ))
            return

        @_tratar_falha_de_ligacao
        def apagar_todas(e):
            execute("DELETE FROM provas")
            S.pop("_edit_prova", None)
            nome.value = local.value = data_.value = ""
            ano.value = str(date.today().year)
            estado.value = "Planeada"
            page.pop_dialog()
            carregar()
            if on_prova_apagada:
                on_prova_apagada()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Apagar todas as provas?"),
            content=ft.Text(
                f"Tem a certeza de que pretende apagar as {quantidade} prova(s)? "
                "Serão também apagadas todas as inscrições, chegadas, ocorrências "
                "e classificações associadas. Esta ação não pode ser desfeita."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.TextButton(
                    "Apagar todas as provas", on_click=apagar_todas,
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    @_tratar_falha_de_ligacao
    def confirmar_apagamento(e):
        prova_id = e.control.data
        prova = query("SELECT nome, ano FROM provas WHERE id=%s",
                      (prova_id,), one=True)
        if not prova:
            carregar()
            return

        @_tratar_falha_de_ligacao
        def apagar(e):
            execute("DELETE FROM provas WHERE id=%s", (prova_id,))
            if S.get("_edit_prova") == prova_id:
                S.pop("_edit_prova", None)
                nome.value = local.value = data_.value = ""
                ano.value = str(date.today().year)
                estado.value = "Planeada"
            page.pop_dialog()
            carregar()
            if on_prova_apagada:
                on_prova_apagada()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Apagar prova?"),
            content=ft.Text(
                f"Tem a certeza de que pretende apagar «{prova['nome']}» "
                f"({prova['ano']})? As inscrições, chegadas, ocorrências e "
                "classificações associadas também serão apagadas. Esta ação "
                "não pode ser desfeita."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.TextButton(
                    "Apagar prova", on_click=apagar,
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    @_tratar_falha_de_ligacao
    def editar(e):
        p = query("SELECT * FROM provas WHERE id=%s", (e.control.data,), one=True)
        nome.value, ano.value = p["nome"], str(p["ano"])
        local.value = p["local"] or ""
        data_.value = str(p["data"]) if p["data"] else ""
        estado.value = p["estado"]
        S["_edit_prova"] = p["id"]
        page.update()

    @_tratar_falha_de_ligacao
    def guardar(e):
        if not nome.value.strip() or not ano.value.strip().isdigit():
            return
        d = data_.value.strip() or None
        if S.get("_edit_prova"):
            execute("UPDATE provas SET nome=%s, ano=%s, data=%s, local=%s, estado=%s WHERE id=%s",
                    (nome.value.strip(), int(ano.value), d, local.value.strip() or None,
                     estado.value, S["_edit_prova"]))
            S.pop("_edit_prova", None)
        else:
            execute("INSERT INTO provas (nome, ano, data, local, estado) VALUES (%s,%s,%s,%s,%s)",
                    (nome.value.strip(), int(ano.value), d, local.value.strip() or None, estado.value))
        nome.value = local.value = data_.value = ""
        carregar()

    def nova(e):
        S.pop("_edit_prova", None)
        nome.value = local.value = data_.value = ""
        ano.value = str(date.today().year)
        estado.value = "Planeada"
        page.update()

    @_tratar_falha_de_ligacao
    def confirmar_reiniciar_operacional(e):
        if not S["prova_id"]:
            _mostrar_mensagem(page, "Selecione uma prova primeiro.", False)
            return

        @_tratar_falha_de_ligacao
        def reiniciar(e):
            pid = S["prova_id"]
            execute("DELETE FROM classificacoes_individuais WHERE prova_id=%s", (pid,))
            execute("DELETE FROM classificacoes_coletivas WHERE prova_id=%s", (pid,))
            execute("DELETE FROM chegadas WHERE prova_id=%s", (pid,))
            execute("DELETE FROM ocorrencias WHERE prova_id=%s", (pid,))
            execute("DELETE FROM partidas WHERE prova_id=%s", (pid,))
            execute("UPDATE inscricoes SET estado='Inscrito' WHERE prova_id=%s", (pid,))
            page.pop_dialog()
            _mostrar_mensagem(page, "Dados operacionais da prova reiniciados.")

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Reiniciar dados operacionais?"),
            content=ft.Text(
                "Serão apagadas as partidas, chegadas, ocorrências e classificações "
                "da prova selecionada. Os inscritos serão mantidos e regressarão "
                "ao estado «Inscrito». Esta ação não pode ser desfeita."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.TextButton(
                    "Reiniciar", on_click=reiniciar,
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    carregar()
    return ft.Column([
        ft.Text("Provas", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([nome, ano, local, data_, estado,
                ft.Button("Guardar", on_click=guardar),
                ft.OutlinedButton("Nova", on_click=nova)]),
        ft.Row([
            ft.OutlinedButton(
                "Apagar todas as provas",
                icon=ft.Icons.DELETE_SWEEP,
                on_click=confirmar_apagar_todas,
                style=ft.ButtonStyle(color=VERMELHO),
            ),
            ft.OutlinedButton(
                "Reiniciar dados operacionais",
                icon=ft.Icons.RESTART_ALT,
                on_click=confirmar_reiniciar_operacional,
                style=ft.ButtonStyle(color=VERMELHO),
            ),
        ]),
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)
    
def inscricoes_view(page):
    pid = S["prova_id"]

    pesquisa = ft.TextField(
        label="Pesquisar por nome, número ou dorsal",
        prefix_icon=ft.Icons.SEARCH,
        width=330,
    )
    ciclo_inscricao = ft.Dropdown(
        label="Filtrar por ciclo",
        options=[
            ft.dropdown.Option("2", "2.º ciclo"),
            ft.dropdown.Option("3", "3.º ciclo"),
            ft.dropdown.Option("secundario", "Secundário"),
        ],
        width=200,
    )
    ano_inscricao = ft.Dropdown(
        label="Ano",
        hint_text="Seleciona o ciclo",
        disabled=True,
        visible=False,
        width=160,
    )
    turma_inscricao = ft.Dropdown(
        label="Turma",
        hint_text="Seleciona o ano",
        disabled=True,
        visible=False,
        width=160,
    )
    turmas_por_letra = {}
    contador_alunos = ft.Text(size=12, color="#637168")
    lista = ft.Column()
    tabela_alunos = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Aluno", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Escalão calculado M", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Escalão calculado F", weight=ft.FontWeight.BOLD)),
            ft.DataColumn(ft.Text("Desporto adaptado", weight=ft.FontWeight.BOLD)),
        ],
        rows=[],
        heading_row_color=VERDE_CLARO,
        heading_text_style=ft.TextStyle(
            color=VERDE_ESCURO,
            weight=ft.FontWeight.BOLD,
        ),
        data_row_min_height=72,
        data_row_max_height=88,
        column_spacing=30,
        horizontal_margin=18,
        divider_thickness=0.7,
        show_bottom_border=True,
        bgcolor=ft.Colors.WHITE,
    )
    selecoes_alunos = {}

    def escolher_genero(e, outra_caixa):
        if e.control.value:
            outra_caixa.value = False
            page.update()

    def atualizar_selecao_da(e):
        page.update()

    def alterar_ciclo(e):
        anos = CICLOS_ANOS.get(ciclo_inscricao.value, ())
        ano_inscricao.options = [
            ft.dropdown.Option(ano, f"{ano}.º ano") for ano in anos
        ]
        ano_inscricao.value = None
        ano_inscricao.disabled = not bool(anos)
        ano_inscricao.visible = bool(anos)
        turma_inscricao.options = []
        turma_inscricao.value = None
        turma_inscricao.disabled = True
        turma_inscricao.visible = False
        turma_inscricao.hint_text = "Seleciona o ano"
        turmas_por_letra.clear()
        page.update()

    @_tratar_falha_de_ligacao
    def alterar_ano(e):
        turma_inscricao.options = []
        turma_inscricao.value = None
        turmas_por_letra.clear()
        ano = ano_inscricao.value
        if ano:
            for turma in query("SELECT id, codigo, nome FROM turmas ORDER BY codigo"):
                ano_turma, letra = _identificar_turma(
                    turma["codigo"], turma["nome"]
                )
                if ano_turma == ano:
                    turmas_por_letra.setdefault(letra, []).append(turma["id"])
            turma_inscricao.options = [
                ft.dropdown.Option(letra, letra)
                for letra in sorted(turmas_por_letra)
            ]
        turma_inscricao.disabled = not bool(turma_inscricao.options)
        turma_inscricao.visible = bool(ano)
        turma_inscricao.hint_text = (
            "Seleciona a turma" if turma_inscricao.options
            else "Sem turmas para este ano"
        )
        page.update()

    def carregar():
        lista.controls.clear()
        if not pid:
            page.update()
            return
        termo = (pesquisa.value or "").strip()
        filtro = ""
        params = [pid]
        if termo:
            filtro = """ AND (a.nome LIKE %s OR a.numero_aluno LIKE %s
                             OR CAST(i.dorsal AS CHAR) LIKE %s)"""
            params.extend((f"%{termo}%", f"%{termo}%", f"%{termo}%"))
        for i in query("""SELECT i.id, i.dorsal, i.estado, i.indicador_da, a.nome, a.numero_aluno,
                                 e.nome AS escalao
                          FROM inscricoes i
                          JOIN alunos a ON a.id=i.aluno_id
                          LEFT JOIN escaloes e ON e.id=i.escalao_id
                          WHERE i.prova_id=%s""" + filtro + " ORDER BY i.dorsal", tuple(params)):
            lista.controls.append(ft.ListTile(
                title=ft.Text(f"#{i['dorsal']} · {i['nome']}"),
                subtitle=ft.Text(f"nº {i['numero_aluno']} · {i['escalao'] or '-'} · {i['estado']}"
                                 f"{' · DA' if i['indicador_da'] else ''}"),
                trailing=ft.IconButton(ft.Icons.DELETE, data=i["id"], on_click=apagar,
                                       icon_color=VERMELHO),
            ))
        page.update()

    @_tratar_falha_de_ligacao
    def carregar_alunos_para_inscrever(e=None):
        tabela_alunos.rows.clear()
        selecoes_alunos.clear()
        filtro_turma = ""
        parametros = [pid, pid]
        if turma_inscricao.value:
            ids_turmas = turmas_por_letra.get(turma_inscricao.value, [])
            if ids_turmas:
                placeholders = ", ".join(["%s"] * len(ids_turmas))
                filtro_turma = f" WHERE t.id IN ({placeholders})"
                parametros.extend(ids_turmas)

        alunos = query(
            """SELECT a.id, a.numero_aluno, a.nome, a.genero, a.data_nascimento,
                      a.ano_letivo, t.codigo AS turma_codigo, t.nome AS turma_nome,
                      em.nome AS escalao_m, ef.nome AS escalao_f,
                      i.id AS inscricao_id, i.dorsal
               FROM alunos a
               JOIN turmas t ON t.id=a.turma_id
               LEFT JOIN inscricoes i ON i.aluno_id=a.id AND i.prova_id=%s
               """
            """LEFT JOIN provas p ON p.id=%s
               LEFT JOIN escaloes em
                 ON em.genero='M'
                AND em.idade_minima<=p.ano-YEAR(a.data_nascimento)
                AND em.idade_maxima>=p.ano-YEAR(a.data_nascimento)
               LEFT JOIN escaloes ef
                 ON ef.genero='F'
                AND ef.idade_minima<=p.ano-YEAR(a.data_nascimento)
                AND ef.idade_maxima>=p.ano-YEAR(a.data_nascimento)"""
            + filtro_turma + " ORDER BY t.codigo, a.nome",
            tuple(parametros),
        )
        contador_alunos.value = (
            f"{len(alunos)} aluno(s) encontrado(s)"
            + (
                f" · {CICLOS_NOMES[ciclo_inscricao.value]}, "
                f"{ano_inscricao.value}.º ano, turma {turma_inscricao.value}"
                if turma_inscricao.value else " · Todas as turmas"
            )
        )
        for aluno in alunos:
            ja_inscrito = aluno["inscricao_id"] is not None
            caixa_m = ft.Checkbox(
                value=False,
                disabled=ja_inscrito,
                active_color=VERDE,
            )
            caixa_f = ft.Checkbox(
                value=False,
                disabled=ja_inscrito,
                active_color=VERDE,
            )
            caixa_da = ft.Checkbox(
                value=False,
                disabled=ja_inscrito,
                active_color=VERDE,
            )
            caixa_m.on_change = lambda e, outra=caixa_f: escolher_genero(e, outra)
            caixa_f.on_change = lambda e, outra=caixa_m: escolher_genero(e, outra)
            caixa_da.on_change = atualizar_selecao_da
            selecoes_alunos[aluno["id"]] = {
                "M": caixa_m,
                "F": caixa_f,
                "DA": caixa_da,
            }
            estado = (
                f"Já inscrito · dorsal #{aluno['dorsal']}"
                if ja_inscrito else "Disponível para inscrição"
            )
            cor_estado = "#637168" if ja_inscrito else VERDE_ESCURO
            tabela_alunos.rows.append(ft.DataRow(
                cells=[
                    ft.DataCell(ft.Column([
                        ft.Text(aluno["nome"], weight=ft.FontWeight.BOLD),
                        ft.Text(
                            f"Nº {aluno['numero_aluno']} · {aluno['turma_codigo']}",
                            size=12, color="#637168",
                        ),
                        ft.Text(
                            estado,
                            size=11, color=cor_estado,
                        ),
                    ], spacing=3)),
                    ft.DataCell(ft.Column([
                        ft.Text(
                            aluno["escalao_m"] or "Sem escalão",
                            color=VERDE_ESCURO,
                            weight=ft.FontWeight.W_500,
                        ),
                        caixa_m,
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)),
                    ft.DataCell(ft.Column([
                        ft.Text(
                            aluno["escalao_f"] or "Sem escalão",
                            color=VERDE_ESCURO,
                            weight=ft.FontWeight.W_500,
                        ),
                        caixa_f,
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)),
                    ft.DataCell(ft.Column([
                        ft.Text("Assinalar", size=12, color="#637168"),
                        caixa_da,
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)),
                ],
            ))
        page.update()

    @_tratar_falha_de_ligacao
    def inscrever_alunos_selecionados(e):
        if not pid:
            _mostrar_mensagem(page, "Cria ou seleciona uma prova primeiro.", False)
            return
        selecionados = [
            (aluno_id, caixas) for aluno_id, caixas in selecoes_alunos.items()
            if caixas["M"].value or caixas["F"].value or caixas["DA"].value
        ]
        if not selecionados:
            _mostrar_mensagem(
                page,
                "Seleciona um escalão ou Desporto Adaptado para pelo menos um aluno.",
                False,
            )
            return

        prova = query("SELECT ano FROM provas WHERE id=%s", (pid,), one=True)
        proximo_dorsal = query(
            "SELECT COALESCE(MAX(dorsal),0)+1 AS n FROM inscricoes WHERE prova_id=%s",
            (pid,), one=True,
        )["n"]
        adicionados = 0
        ignorados = 0
        for aluno_id, caixas in selecionados:
            aluno = query(
                """SELECT id, genero, data_nascimento FROM alunos WHERE id=%s""",
                (aluno_id,), one=True,
            )
            if not aluno or query(
                "SELECT id FROM inscricoes WHERE prova_id=%s AND aluno_id=%s",
                (pid, aluno_id), one=True,
            ):
                ignorados += 1
                continue

            genero_escalao = (
                "M" if caixas["M"].value else
                "F" if caixas["F"].value else aluno["genero"]
            )
            idade = prova["ano"] - aluno["data_nascimento"].year
            escalao = query(
                """SELECT id FROM escaloes
                   WHERE genero=%s AND idade_minima<=%s AND idade_maxima>=%s""",
                (genero_escalao, idade, idade), one=True,
            )
            execute(
                """INSERT INTO inscricoes
                   (prova_id, aluno_id, escalao_id, dorsal, qr_code,
                    indicador_da, estado)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    pid, aluno_id, escalao["id"] if escalao else None,
                    proximo_dorsal, f"RC{pid}-{proximo_dorsal}",
                    caixas["DA"].value, "Inscrito",
                ),
            )
            proximo_dorsal += 1
            adicionados += 1

        carregar()
        carregar_alunos_para_inscrever()
        _mostrar_mensagem(
            page,
            f"Inscrição concluída: {adicionados} aluno(s) inscrito(s), "
            f"{ignorados} ignorado(s).",
        )

    @_tratar_falha_de_ligacao
    def apagar(e):
        if not pid:
            _mostrar_mensagem(page, "Cria ou seleciona uma prova primeiro.", False)
            return
        execute("DELETE FROM inscricoes WHERE id=%s", (e.control.data,))
        carregar()

    @_tratar_falha_de_ligacao
    def confirmar_apagar_todos(e):
        if not pid:
            _mostrar_mensagem(page, "Cria ou seleciona uma prova primeiro.", False)
            return
        quantidade = query(
            "SELECT COUNT(*) AS total FROM inscricoes WHERE prova_id=%s",
            (pid,), one=True,
        )["total"]

        if quantidade == 0:
            page.show_dialog(ft.SnackBar(
                content="Não existem inscritos nesta prova.",
                duration=4000,
            ))
            return

        @_tratar_falha_de_ligacao
        def apagar_todos(e):
            execute("DELETE FROM inscricoes WHERE prova_id=%s", (pid,))
            page.pop_dialog()
            carregar()

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Apagar todos os inscritos?"),
            content=ft.Text(
                f"Tem a certeza de que pretende apagar os {quantidade} inscrito(s) "
                "desta prova? Chegadas, ocorrências e classificações associadas "
                "também serão apagadas. Esta ação não pode ser desfeita."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.pop_dialog()),
                ft.TextButton(
                    "Apagar todos", on_click=apagar_todos,
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    picker = S.get("_inscricoes_picker")
    if picker is None:
        picker = ft.FilePicker()
        page.services.append(picker)
        S["_inscricoes_picker"] = picker

    @_tratar_falha_de_ligacao
    async def exportar_csv(e):
        if not pid:
            _mostrar_mensagem(page, "Cria ou seleciona uma prova primeiro.", False)
            return
        linhas = query("""SELECT a.numero_aluno, a.nome, t.codigo AS turma_codigo,
                                 t.nome AS turma_nome, t.ano_letivo,
                                 i.dorsal, i.estado, i.indicador_da
                          FROM inscricoes i
                          JOIN alunos a ON a.id=i.aluno_id
                          JOIN turmas t ON t.id=a.turma_id
                          WHERE i.prova_id=%s
                          ORDER BY i.dorsal""", (pid,))
        conteudo = io.StringIO(newline="")
        escritor = csv.writer(conteudo, delimiter=";", lineterminator="\n")
        escritor.writerow((
            "numero_aluno", "nome", "turma_codigo", "turma_nome",
            "ano_letivo", "dorsal", "estado", "da",
        ))
        for linha in linhas:
            escritor.writerow((
                linha["numero_aluno"], linha["nome"], linha["turma_codigo"],
                linha["turma_nome"], linha["ano_letivo"], linha["dorsal"],
                linha["estado"], "Sim" if linha["indicador_da"] else "Nao",
            ))
        nome = f"inscricoes_prova{pid}.csv"
        caminho = await picker.save_file(
            dialog_title="Exportar inscrições",
            file_name=nome,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"],
            src_bytes=conteudo.getvalue().encode("utf-8-sig"),
        )
        if caminho:
            try:
                with open(caminho, "wb") as ficheiro:
                    ficheiro.write(conteudo.getvalue().encode("utf-8-sig"))
                _mostrar_mensagem(page, "Inscrições exportadas com sucesso.")
            except OSError as erro:
                _mostrar_mensagem(page, f"Não foi possível guardar: {erro}", False)
        elif not page.web:
            _mostrar_mensagem(page, "Exportação cancelada.", False)

    @_tratar_falha_de_ligacao
    async def importar_csv(e):
        if not pid:
            _mostrar_mensagem(
                page,
                "Cria uma prova em Configurações e seleciona-a antes de carregar o CSV.",
                False,
            )
            return
        ficheiros = await picker.pick_files(
            dialog_title="Selecionar CSV com 500 alunos",
            allowed_extensions=["csv"],
            file_type=ft.FilePickerFileType.CUSTOM,
            allow_multiple=False,
        )
        if not ficheiros:
            return
        caminho = ficheiros[0].path
        if not caminho:
            _mostrar_mensagem(page, "Não foi possível ler o ficheiro selecionado.", False)
            return
        try:
            with open(caminho, "r", encoding="utf-8-sig", newline="") as ficheiro:
                leitor = csv.DictReader(ficheiro, delimiter=";")
                importados = 0
                ignorados = 0
                linhas = list(leitor)
        except (OSError, csv.Error) as erro:
            _mostrar_mensagem(page, f"Erro ao importar: {erro}", False)
            return

        if len(linhas) != 500:
            _mostrar_mensagem(
                page,
                f"O CSV deve conter exatamente 500 alunos; foram encontrados {len(linhas)}.",
                False,
            )
            return

        campos = {
            "numero_aluno", "nome", "genero", "data_nascimento",
            "turma_codigo", "turma_nome", "ano_letivo",
        }
        if not campos.issubset(set(leitor.fieldnames or [])):
            _mostrar_mensagem(
                page,
                "Colunas obrigatórias: numero_aluno; nome; genero; data_nascimento; "
                "turma_codigo; turma_nome; ano_letivo; da",
                False,
            )
            return

        contagem_turmas = {}
        numeros = set()
        dados_validados = []
        for numero_linha, linha in enumerate(linhas, 2):
            numero = (linha.get("numero_aluno") or "").strip()
            nome = (linha.get("nome") or "").strip()
            genero = (linha.get("genero") or "").strip().upper()
            nascimento = (linha.get("data_nascimento") or "").strip()
            turma_codigo = (linha.get("turma_codigo") or "").strip()
            turma_nome = (linha.get("turma_nome") or "").strip()
            ano_letivo = (linha.get("ano_letivo") or "").strip()

            if not all((numero, nome, genero, nascimento, turma_codigo, turma_nome, ano_letivo)):
                _mostrar_mensagem(page, f"Linha {numero_linha}: existem campos vazios.", False)
                return
            if genero not in ("M", "F"):
                _mostrar_mensagem(page, f"Linha {numero_linha}: género deve ser M ou F.", False)
                return
            try:
                datetime.strptime(nascimento, "%Y-%m-%d")
            except ValueError:
                _mostrar_mensagem(
                    page,
                    f"Linha {numero_linha}: data_nascimento inválida (AAAA-MM-DD).",
                    False,
                )
                return
            if numero in numeros:
                _mostrar_mensagem(
                    page,
                    f"Linha {numero_linha}: número de aluno {numero} repetido.",
                    False,
                )
                return
            numeros.add(numero)
            contagem_turmas[turma_codigo] = contagem_turmas.get(turma_codigo, 0) + 1
            dados_validados.append({
                "numero": numero,
                "nome": nome,
                "genero": genero,
                "nascimento": nascimento,
                "turma_codigo": turma_codigo,
                "turma_nome": turma_nome,
                "ano_letivo": ano_letivo,
                "da": (linha.get("da") or "").strip().lower() in ("sim", "yes", "1", "true"),
            })

        turmas_invalidas = [
            f"{codigo}: {quantidade}"
            for codigo, quantidade in sorted(contagem_turmas.items())
            if quantidade < 8 or quantidade > 22
        ]
        if turmas_invalidas:
            _mostrar_mensagem(
                page,
                "Cada turma deve ter entre 8 e 22 alunos. "
                "Inválidas: " + "; ".join(turmas_invalidas),
                False,
            )
            return

        ignorados = 0
        importados = 0
        prova = query("SELECT ano FROM provas WHERE id=%s", (pid,), one=True)
        m = query(
            "SELECT COALESCE(MAX(dorsal),0)+1 AS n "
            "FROM inscricoes WHERE prova_id=%s",
            (pid,), one=True,
        )["n"]

        for dados in dados_validados:
            turma = query(
                "SELECT id FROM turmas "
                "WHERE codigo=%s AND ano_letivo=%s",
                (dados["turma_codigo"], dados["ano_letivo"]),
                one=True,
            )
            if not turma:
                turma_id = execute(
                    "INSERT INTO turmas (codigo, nome, ano_letivo) VALUES (%s,%s,%s)",
                    (dados["turma_codigo"], dados["turma_nome"], dados["ano_letivo"]),
                )
            else:
                turma_id = turma["id"]

            aluno = query(
                "SELECT id FROM alunos "
                "WHERE numero_aluno=%s AND ano_letivo=%s",
                (dados["numero"], dados["ano_letivo"]),
                one=True,
            )
            if aluno:
                aluno_id = aluno["id"]
                execute(
                    "UPDATE alunos SET nome=%s, genero=%s, data_nascimento=%s, "
                    "turma_id=%s WHERE id=%s",
                    (
                        dados["nome"], dados["genero"], dados["nascimento"],
                        turma_id, aluno_id,
                    ),
                )
            else:
                aluno_id = execute(
                    "INSERT INTO alunos "
                    "(numero_aluno, nome, genero, data_nascimento, turma_id, ano_letivo) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (
                        dados["numero"], dados["nome"], dados["genero"],
                        dados["nascimento"], turma_id, dados["ano_letivo"],
                    ),
                )

            if query(
                "SELECT id FROM inscricoes WHERE prova_id=%s AND aluno_id=%s",
                (pid, aluno_id), one=True,
            ):
                ignorados += 1
                continue

            idade = datetime.strptime(dados["nascimento"], "%Y-%m-%d").year
            idade = prova["ano"] - idade
            esc = query(
                "SELECT id FROM escaloes "
                "WHERE genero=%s AND idade_minima<=%s AND idade_maxima>=%s",
                (dados["genero"], idade, idade), one=True,
            )
            execute(
                "INSERT INTO inscricoes "
                "(prova_id, aluno_id, escalao_id, dorsal, qr_code, indicador_da, estado) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (
                    pid, aluno_id, esc["id"] if esc else None, m,
                    f"RC{pid}-{m}", dados["da"], "Inscrito",
                ),
            )
            m += 1
            importados += 1

        carregar()
        _mostrar_mensagem(
            page,
            f"Importação concluída: {importados} inscrito(s) adicionado(s), "
            f"{ignorados} ignorado(s).",
        )

    async def descarregar_modelo(e):
        nome = "inscricoes_500_alunos.csv"
        caminho_modelo = __import__("os").path.join(
            __import__("os").path.dirname(__file__), nome
        )
        try:
            with open(caminho_modelo, "r", encoding="utf-8-sig", newline="") as ficheiro:
                conteudo = ficheiro.read().encode("utf-8-sig")
        except OSError as erro:
            _mostrar_mensagem(page, f"Não foi possível abrir o modelo: {erro}", False)
            return

        caminho = await picker.save_file(
            dialog_title="Guardar modelo de inscrições",
            file_name=nome,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["csv"],
            src_bytes=conteudo,
        )
        if caminho:
            try:
                with open(caminho, "wb") as ficheiro:
                    ficheiro.write(conteudo)
                _mostrar_mensagem(page, "Modelo CSV guardado.")
            except OSError as erro:
                _mostrar_mensagem(page, f"Não foi possível guardar: {erro}", False)
        elif not page.web:
            _mostrar_mensagem(page, "Transferência cancelada.", False)

    ciclo_inscricao.on_select = alterar_ciclo
    ano_inscricao.on_select = alterar_ano
    turma_inscricao.on_select = carregar_alunos_para_inscrever
    pesquisa.on_change = lambda e: carregar()
    carregar()
    carregar_alunos_para_inscrever()
    return ft.Column([
        ft.Text("Inscrições", size=20, weight=ft.FontWeight.BOLD),
        *([] if pid else [ft.Text(
            "Cria uma prova em Configurações e seleciona-a no topo para carregar os alunos.",
            color=VERMELHO,
        )]),
        ft.Row([
            pesquisa,
            ft.OutlinedButton(
                "Exportar CSV",
                icon=ft.Icons.DOWNLOAD,
                on_click=exportar_csv,
                disabled=not pid,
            ),
            ft.Button(
                "Carregar CSV — 500 alunos",
                icon=ft.Icons.UPLOAD,
                on_click=importar_csv,
                bgcolor=VERDE,
                color=ft.Colors.WHITE,
            ),
            ft.OutlinedButton(
                "Descarregar modelo 500 alunos",
                icon=ft.Icons.FILE_DOWNLOAD,
                on_click=descarregar_modelo,
            ),
            ft.OutlinedButton(
                "Apagar todos os inscritos",
                icon=ft.Icons.DELETE_SWEEP,
                on_click=confirmar_apagar_todos,
                style=ft.ButtonStyle(color=VERMELHO),
                disabled=not pid,
            ),
        ]),
        ft.Divider(),
        ft.Container(
            content=ft.Column([
                ft.Text("Alunos para inscrição", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Seleciona o ciclo, o ano e a turma. Escolhe um escalão M ou F; "
                    "Desporto Adaptado pode ser marcado em separado.",
                    size=13,
                    color="#637168",
                ),
                ft.Row([
                    ciclo_inscricao,
                    ano_inscricao,
                    turma_inscricao,
                    ft.Button(
                        "Pesquisar",
                        icon=ft.Icons.SEARCH,
                        on_click=carregar_alunos_para_inscrever,
                        bgcolor=VERDE_ESCURO,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Button(
                        "Inscrever selecionados",
                        icon=ft.Icons.PERSON_ADD,
                        on_click=inscrever_alunos_selecionados,
                        bgcolor=VERDE,
                        color=ft.Colors.WHITE,
                        disabled=not pid,
                    ),
                ], wrap=True, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                contador_alunos,
                ft.Container(
                    content=ft.Row([tabela_alunos], scroll=ft.ScrollMode.AUTO),
                    padding=8,
                    border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=12,
                    bgcolor=ft.Colors.WHITE,
                ),
            ], spacing=12),
            padding=18,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        ),
        ft.Divider(),
        ft.Text("Inscrições nesta prova", weight=ft.FontWeight.BOLD),
        lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def partida_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Text("Sem prova.")
    txt = ft.TextField(label="Nº dorsal ou QR (RCx-n)", width=280)
    lista = ft.Column()

    def carregar():
        lista.controls.clear()
        for i in query("""SELECT i.id, i.dorsal, a.nome, i.estado
                          FROM inscricoes i JOIN alunos a ON a.id=i.aluno_id
                          WHERE i.prova_id=%s AND i.estado IN ('Inscrito','Participante')
                          ORDER BY i.dorsal""", (pid,)):
            lista.controls.append(ft.ListTile(
                title=ft.Text(f"#{i['dorsal']} · {i['nome']}"),
                subtitle=ft.Text(i["estado"]),
                trailing=(ft.IconButton(ft.Icons.CHECK, data=i["id"], on_click=marcar)
                          if i["estado"] == "Inscrito" else None),
            ))
        p = query("SELECT hora_inicio FROM partidas WHERE prova_id=%s", (pid,), one=True)
        if p:
            lista.controls.insert(0, ft.Text(f"Partida dada às {p['hora_inicio']}",
                                             color=ft.Colors.GREEN_700))
        page.update()

    @_tratar_falha_de_ligacao
    def marcar(e):
        execute("UPDATE inscricoes SET estado='Participante' WHERE id=%s", (e.control.data,))
        carregar()

    @_tratar_falha_de_ligacao
    def por_texto(e):
        v = (txt.value or "").strip()
        if not v:
            return
        row = query("SELECT id FROM inscricoes WHERE prova_id=%s AND (qr_code=%s OR dorsal=%s)",
                    (pid, v, v if v.isdigit() else -1), one=True)
        if row:
            execute("UPDATE inscricoes SET estado='Participante' WHERE id=%s", (row["id"],))
            txt.value = ""; carregar()

    @_tratar_falha_de_ligacao
    def dar_partida(e):
        if not query("SELECT id FROM partidas WHERE prova_id=%s", (pid,), one=True):
            execute("INSERT INTO partidas (prova_id, hora_inicio) VALUES (%s, NOW())", (pid,))
        carregar()

    carregar()
    return ft.Column([
        ft.Text("Partida", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([txt, ft.Button("Entregar", on_click=por_texto),
                ft.Button("Dar partida", on_click=dar_partida,
                                  bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE)]),
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def meta_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Text("Sem prova.")
    txt = ft.TextField(label="QR / dorsal", width=260, autofocus=True)
    motivo = ft.TextField(label="Motivo (ocorrência)", width=260)
    lista = ft.Column()

    def carregar():
        lista.controls.clear()
        for c in query("""SELECT c.ordem, a.nome, i.dorsal, o.tipo AS ocorrencia_tipo
                          FROM chegadas c
                          JOIN inscricoes i ON i.id=c.inscricao_id
                          JOIN alunos a ON a.id=i.aluno_id
                          LEFT JOIN ocorrencias o
                            ON o.prova_id=c.prova_id AND o.inscricao_id=i.id
                          WHERE c.prova_id=%s ORDER BY c.ordem""", (pid,)):
            ocorrencia = {
                "Desistencia": "Desistência",
                "Desclassificacao": "Desclassificação",
            }.get(c["ocorrencia_tipo"])
            lista.controls.append(ft.ListTile(
                leading=ft.CircleAvatar(content=ft.Text(str(c["ordem"]))),
                title=ft.Text(f"{c['nome']} (#{c['dorsal']})"),
                subtitle=ft.Text(ocorrencia) if ocorrencia else None,
            ))
        page.update()

    @_tratar_falha_de_ligacao
    def chegada(e):
        v = (txt.value or "").strip()
        if not v:
            return
        row = query("SELECT id FROM inscricoes WHERE prova_id=%s AND (qr_code=%s OR dorsal=%s)",
                    (pid, v, v if v.isdigit() else -1), one=True)
        if not row:
            return
        if query("SELECT 1 FROM chegadas WHERE prova_id=%s AND inscricao_id=%s",
                 (pid, row["id"]), one=True):
            return
        ord_ = query("SELECT COALESCE(MAX(ordem),0)+1 AS n FROM chegadas WHERE prova_id=%s",
                     (pid,), one=True)["n"]
        execute("INSERT INTO chegadas (prova_id, inscricao_id, ordem) VALUES (%s,%s,%s)",
                (pid, row["id"], ord_))
        txt.value = ""; carregar()

    @_tratar_falha_de_ligacao
    def ocorrencia(tipo):
        v = (txt.value or "").strip()
        if not v:
            _mostrar_mensagem(page, "Indique o QR ou dorsal do aluno.", False)
            return
        row = query("SELECT id FROM inscricoes WHERE prova_id=%s AND (qr_code=%s OR dorsal=%s)",
                    (pid, v, v if v.isdigit() else -1), one=True)
        if not row:
            _mostrar_mensagem(page, f"Não foi encontrada inscrição para «{v}».", False)
            return
        execute("""INSERT INTO ocorrencias (prova_id, inscricao_id, tipo, motivo)
                   VALUES (%s,%s,%s,%s)
                   ON DUPLICATE KEY UPDATE tipo=VALUES(tipo), motivo=VALUES(motivo)""",
                (pid, row["id"], tipo, (motivo.value or "").strip() or None))
        txt.value = ""; motivo.value = ""; carregar()
        nome_tipo = {
            "Desistencia": "Desistência",
            "Desclassificacao": "Desclassificação",
        }[tipo]
        _mostrar_mensagem(page, f"{nome_tipo} registada para «{v}».")

    carregar()
    return ft.Column([
        ft.Text("Meta", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([txt,
                ft.Button("Chegada", on_click=chegada),
                ft.OutlinedButton("Desistência", icon=ft.Icons.EXIT_TO_APP,
                                  on_click=lambda e: ocorrencia("Desistencia"),
                                  style=ft.ButtonStyle(color=VERMELHO)),
                ft.OutlinedButton("Desclassificação", icon=ft.Icons.BLOCK,
                                  on_click=lambda e: ocorrencia("Desclassificacao"),
                                  style=ft.ButtonStyle(color=VERMELHO)),
                motivo]),
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def classificacoes_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Text("Sem prova.")
    tab = ft.Column()

    @_tratar_falha_de_ligacao
    def calcular():
        calcular_classificacoes(pid)
        render()

    def render():
        tab.controls.clear()
        tab.controls.append(ft.Text("Individuais", weight=ft.FontWeight.BOLD))
        for r in query("""SELECT ci.posicao_geral, ci.posicao_escalao, ci.posicao_genero,
                                 ci.apurado, a.nome, i.dorsal, e.nome AS escalao
                          FROM classificacoes_individuais ci
                          JOIN inscricoes i ON i.id=ci.inscricao_id
                          JOIN alunos a ON a.id=i.aluno_id
                          LEFT JOIN escaloes e ON e.id=i.escalao_id
                          WHERE ci.prova_id=%s ORDER BY ci.posicao_geral""", (pid,)):
            tab.controls.append(ft.ListTile(
                leading=ft.CircleAvatar(content=ft.Text(str(r["posicao_geral"]))),
                title=ft.Text(f"{r['nome']} (#{r['dorsal']})"),
                subtitle=ft.Text(f"{r['escalao'] or '-'} · Esc {r['posicao_escalao']} · "
                                 f"Gen {r['posicao_genero']}"
                                 f"{' · APURADO' if r['apurado'] else ''}"),
            ))
        tab.controls.append(ft.Divider())
        tab.controls.append(ft.Text("Coletivas", weight=ft.FontWeight.BOLD))
        for r in query("""SELECT cc.posicao, cc.pontos, t.codigo, t.nome
                          FROM classificacoes_coletivas cc
                          JOIN turmas t ON t.id=cc.turma_id
                          WHERE cc.prova_id=%s ORDER BY cc.posicao""", (pid,)):
            tab.controls.append(ft.ListTile(
                leading=ft.CircleAvatar(content=ft.Text(str(r["posicao"]))),
                title=ft.Text(f"{r['codigo']} — {r['nome']}"),
                subtitle=ft.Text(f"{r['pontos']} pts (soma dos 4 melhores)"),
            ))
        page.update()

    render()
    return ft.Column([
        ft.Text("Classificações", size=20, weight=ft.FontWeight.BOLD),
        ft.Button("Calcular", on_click=lambda e: calcular()),
        ft.Divider(), tab,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def relatorios_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Text("Sem prova.")
    info = ft.Text("", color=ft.Colors.GREY_700)
    picker = S.get("_relatorio_picker")
    if picker is None:
        picker = ft.FilePicker()
        page.services.append(picker)
        S["_relatorio_picker"] = picker

    def obter_linhas():
        return query("""SELECT ci.posicao_geral, a.nome, i.dorsal, e.nome AS escalao
                        FROM classificacoes_individuais ci
                        JOIN inscricoes i ON i.id=ci.inscricao_id
                        JOIN alunos a ON a.id=i.aluno_id
                        LEFT JOIN escaloes e ON e.id=i.escalao_id
                        WHERE ci.prova_id=%s ORDER BY ci.posicao_geral""", (pid,))

    async def guardar_exportacao(nome, extensao, conteudo):
        caminho = await picker.save_file(
            dialog_title="Guardar relatório",
            file_name=nome,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=[extensao],
            src_bytes=conteudo,
        )
        if caminho:
            try:
                with open(caminho, "wb") as ficheiro:
                    ficheiro.write(conteudo)
            except OSError as erro:
                info.value = f"Não foi possível guardar o ficheiro: {erro}"
                info.color = VERMELHO
            else:
                info.value = f"Ficheiro guardado em: {caminho}"
                info.color = VERDE
        elif page.web:
            info.value = "Transferência iniciada no navegador."
            info.color = VERDE
        else:
            info.value = "Exportação cancelada."
            info.color = ft.Colors.GREY_700
        page.update()

    @_tratar_falha_de_ligacao
    async def exportar_csv(e):
        linhas = obter_linhas()
        nome = f"classificacao_geral_prova{pid}.csv"
        await guardar_exportacao(nome, "csv", gerar_csv_classificacao(linhas))

    @_tratar_falha_de_ligacao
    async def exportar_pdf(e):
        linhas = obter_linhas()
        nome = f"classificacao_geral_prova{pid}.pdf"
        await guardar_exportacao(nome, "pdf", gerar_pdf_classificacao(linhas))

    return ft.Column([
        ft.Text("Relatórios", size=20, weight=ft.FontWeight.BOLD),
        ft.Text("Guarde ou transfira a classificação geral nos formatos disponíveis."),
        ft.Row([
            ft.Button(
                "Transferir CSV", icon=ft.Icons.DOWNLOAD,
                on_click=exportar_csv,
            ),
            ft.OutlinedButton(
                "Transferir PDF", icon=ft.Icons.PICTURE_AS_PDF,
                on_click=exportar_pdf,
                style=ft.ButtonStyle(color=VERMELHO),
            ),
        ], wrap=True, spacing=12),
        info,
    ], expand=True)

def alunos_view(page):
    numero = ft.TextField(label="Nº aluno", width=150)
    nome = ft.TextField(label="Nome", width=280)
    genero = ft.Dropdown(
        label="Género", width=120, value="M",
        options=[ft.dropdown.Option("M", "Masculino"), ft.dropdown.Option("F", "Feminino")],
    )
    nascimento = ft.TextField(label="Nascimento (AAAA-MM-DD)", width=180)
    ano_letivo = ft.TextField(label="Ano letivo", width=130, value=str(date.today().year))
    turma = ft.Dropdown(label="Turma", width=220)
    pesquisa = ft.TextField(
        label="Pesquisar aluno",
        prefix_icon=ft.Icons.SEARCH,
        width=300,
    )
    codigo_turma = ft.TextField(label="Código da turma", width=160)
    nome_turma = ft.TextField(label="Nome da turma", width=220)
    lista = ft.Column()

    def carregar():
        turma.options = [
            ft.dropdown.Option(str(t["id"]), f"{t['codigo']} · {t['nome']} ({t['ano_letivo']})")
            for t in query("SELECT * FROM turmas ORDER BY codigo")
        ]
        lista.controls.clear()
        termo = (pesquisa.value or "").strip()
        filtro = ""
        params = []
        if termo:
            filtro = " WHERE a.nome LIKE %s OR a.numero_aluno LIKE %s"
            params = [f"%{termo}%", f"%{termo}%"]
        for aluno in query(
            """SELECT a.id, a.numero_aluno, a.nome, a.genero,
                      a.data_nascimento, a.ano_letivo, t.codigo AS turma
               FROM alunos a
               JOIN turmas t ON t.id=a.turma_id"""
            + filtro + " ORDER BY a.nome",
            tuple(params),
        ):
            lista.controls.append(ft.ListTile(
                title=ft.Text(f"{aluno['nome']} · nº {aluno['numero_aluno']}"),
                subtitle=ft.Text(
                    f"{aluno['turma']} · "
                    f"{'Masculino' if aluno['genero'] == 'M' else 'Feminino'} · "
                    f"{aluno['data_nascimento']} · {aluno['ano_letivo']}"
                ),
                trailing=ft.IconButton(
                    ft.Icons.DELETE,
                    data=aluno["id"],
                    on_click=confirmar_apagar,
                    icon_color=VERMELHO,
                    tooltip="Apagar aluno",
                ),
            ))
        page.update()

    @_tratar_falha_de_ligacao
    def confirmar_apagar(e):
        aluno_id = e.control.data

        @_tratar_falha_de_ligacao
        def apagar(ev):
            execute("DELETE FROM alunos WHERE id=%s", (aluno_id,))
            page.pop_dialog()
            carregar()
            _mostrar_mensagem(page, "Aluno apagado.")

        page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Apagar aluno?"),
            content=ft.Text(
                "O aluno e todas as suas inscrições serão apagados. "
                "Esta ação não pode ser desfeita."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
                ft.TextButton(
                    "Apagar", on_click=apagar,
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))

    @_tratar_falha_de_ligacao
    def criar_turma(e):
        if not codigo_turma.value.strip() or not nome_turma.value.strip():
            _mostrar_mensagem(page, "Indique o código e o nome da turma.", False)
            return
        if query(
            "SELECT id FROM turmas WHERE codigo=%s AND ano_letivo=%s",
            (codigo_turma.value.strip(), ano_letivo.value.strip()), one=True,
        ):
            _mostrar_mensagem(page, "Esta turma já existe neste ano letivo.", False)
            return
        execute(
            "INSERT INTO turmas (codigo, nome, ano_letivo) VALUES (%s,%s,%s)",
            (codigo_turma.value.strip(), nome_turma.value.strip(), ano_letivo.value.strip()),
        )
        codigo_turma.value = nome_turma.value = ""
        carregar()
        _mostrar_mensagem(page, "Turma criada com sucesso.")

    @_tratar_falha_de_ligacao
    def criar_aluno(e):
        if not numero.value.strip() or not nome.value.strip() or not turma.value:
            _mostrar_mensagem(page, "Preencha o número, nome e turma.", False)
            return
        if query(
            "SELECT id FROM alunos WHERE numero_aluno=%s AND ano_letivo=%s",
            (numero.value.strip(), ano_letivo.value.strip()), one=True,
        ):
            _mostrar_mensagem(page, "Já existe um aluno com este número neste ano letivo.", False)
            return
        try:
            datetime.strptime(nascimento.value.strip(), "%Y-%m-%d")
        except ValueError:
            _mostrar_mensagem(page, "Indique uma data válida no formato AAAA-MM-DD.", False)
            return
        execute(
            "INSERT INTO alunos "
            "(numero_aluno, nome, genero, data_nascimento, turma_id, ano_letivo) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (
                numero.value.strip(), nome.value.strip(), genero.value,
                nascimento.value.strip(), int(turma.value), ano_letivo.value.strip(),
            ),
        )
        numero.value = nome.value = nascimento.value = ""
        carregar()
        _mostrar_mensagem(page, "Aluno criado com sucesso.")

    pesquisa.on_change = lambda e: carregar()
    carregar()
    return ft.Column([
        ft.Text("Alunos", size=20, weight=ft.FontWeight.BOLD),
        ft.Text("Nova turma", weight=ft.FontWeight.BOLD),
        ft.Row([codigo_turma, nome_turma, ano_letivo,
                ft.Button("Criar turma", on_click=criar_turma)], wrap=True),
        ft.Divider(),
        ft.Text("Novo aluno", weight=ft.FontWeight.BOLD),
        ft.Row([numero, nome, genero, nascimento, turma,
                ft.Button("Criar aluno", on_click=criar_aluno)], wrap=True),
        ft.Divider(),
        pesquisa,
        lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)


def responsaveis_view(page):
    nome = ft.TextField(label="Nome", width=200)
    user = ft.TextField(label="Utilizador (n.º aluno para alunos)", width=240)
    pwd = ft.TextField(label="Palavra-passe", password=True, width=160)
    perfil_dd = ft.Dropdown(label="Perfil", width=200)
    lista = ft.Column()

    def carregar():
        perfil_dd.options = [ft.dropdown.Option(str(p["id"]), p["nome"])
                             for p in query("SELECT id, nome FROM perfis")]
        lista.controls.clear()
        for u in query("""SELECT u.id, u.nome, u.username, u.ativo,
                                 GROUP_CONCAT(p.nome) AS perfis
                          FROM utilizadores u
                          LEFT JOIN utilizador_perfil up ON up.utilizador_id=u.id
                          LEFT JOIN perfis p ON p.id=up.perfil_id
                          GROUP BY u.id ORDER BY u.nome"""):
            lista.controls.append(ft.ListTile(
                title=ft.Text(f"{u['nome']} ({u['username']})"),
                subtitle=ft.Text(u["perfis"] or "sem perfis"),
                trailing=ft.IconButton(ft.Icons.DELETE, data=u["id"], on_click=apagar,
                                       disabled=(u["id"] == S["user"]["id"])),
            ))
        page.update()

    @_tratar_falha_de_ligacao
    def apagar(e):
        execute("DELETE FROM utilizadores WHERE id=%s", (e.control.data,))
        carregar()

    @_tratar_falha_de_ligacao
    def criar(e):
        from auth import hash_password
        username = (user.value or "").strip()
        if not (nome.value or "").strip() or not username or len(pwd.value or "") < 6:
            return
        perfil = query(
            "SELECT nome FROM perfis WHERE id=%s",
            (int(perfil_dd.value),),
            one=True,
        ) if perfil_dd.value else None
        if perfil and perfil["nome"] == "Aluno":
            aluno = query(
                "SELECT id FROM alunos WHERE numero_aluno=%s "
                "ORDER BY ano_letivo DESC, id DESC LIMIT 1",
                (username,),
                one=True,
            )
            if not aluno:
                _mostrar_mensagem(
                    page,
                    "Para criar uma conta de aluno, use um número de aluno existente.",
                    False,
                )
                return
        uid = execute("INSERT INTO utilizadores (nome, username, password_hash, ativo) "
                      "VALUES (%s,%s,%s,TRUE)",
                      (nome.value.strip(), username, hash_password(pwd.value)))
        if perfil_dd.value:
            execute("INSERT INTO utilizador_perfil (utilizador_id, perfil_id) VALUES (%s,%s)",
                    (uid, int(perfil_dd.value)))
        nome.value = user.value = pwd.value = ""
        carregar()

    carregar()
    return ft.Column([
        ft.Text("Utilizadores", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([
            nome, user,
            pwd, perfil_dd, ft.Button("Criar", on_click=criar),
        ]),
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def main(page: ft.Page):
    S["_page"] = page
    page.title = APP_TITLE
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=VERDE)
    page.window.width = 1300
    page.window.height = 820
    page.padding = 20

    def logout():
        S["user"] = None
        S["prova_id"] = None
        S.pop("_secao", None)
        login_view(page, home)

    def home():
        home_view(page, logout)

    login_view(page, home)


if __name__ == "__main__":
    ft.run(main)

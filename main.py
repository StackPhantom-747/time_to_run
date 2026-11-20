import base64
import csv
import html
import io
import xml.etree.ElementTree as ET
import zipfile
import flet as ft
from mysql.connector import Error as MySQLError
from mysql.connector import IntegrityError
from datetime import date, datetime
from config import APP_TITLE
from db import query, execute, execute_transaction
from auth import hash_password, verificar
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

S = {"user": None, "prova_id": None}

VERDE = "#16834A"
VERDE_ESCURO = "#11663A"
VERDE_CLARO = "#E8F5EC"
VERMELHO = "#C93C3C"
FUNDO = "#F4F7F2"
TEXTO = "#1F2E29"
TEXTO_MUTO = "#5F7268"
BORDA = "#E2EAE4"
CARD = "#FFFFFF"


def _responsive_width(page, preferred):
    largura = page.width or 1300
    return max(120, min(preferred, largura - 44))


def _ano_a_partir_data(data):
    if not data:
        return None
    try:
        if isinstance(data, datetime):
            return data.year
        return date.fromisoformat(str(data)).year
    except ValueError:
        return None


def _ano_letivo_atual(data=None):
    data = data or date.today()
    inicio = data.year if data.month >= 9 else data.year - 1
    return f"{inicio}/{inicio + 1}"


def _etiqueta_prova(prova):
    nome = str(prova["nome"]).strip() if prova.get("nome") is not None else ""
    data = prova.get("data")
    if data:
        return f"{nome} ({data})"
    ano = prova.get("ano")
    return f"{nome} ({ano})" if ano is not None else nome


def pode(modulo):
    if not S["user"]:
        return False
    perfis = S["user"]["perfis"]
    if "Administrador" in perfis:
        return True
    mapa = {
        "inscricoes": {"Secretariado Inscrições"},
        "partida": {"Secretariado Partida"},
        "meta": {"Secretariado Meta"},
        "classificacoes": {"Secretariado Meta", "Consulta", "Secretariado Inscrições"},
        "relatorios": {"Consulta", "Secretariado Inscrições"},
        "config": {"Administrador"},
        "responsaveis": {"Administrador"},
        "aluno": {"Aluno"},
    }
    return bool(set(perfis) & mapa.get(modulo, set()))


def gerar_csv_classificacao(linhas):
    conteudo = io.StringIO(newline="")
    escritor = csv.writer(conteudo, delimiter=";", lineterminator="\n")
    escritor.writerow(("posicao", "nome", "dorsal", "escalao"))
    for linha in linhas:
        escritor.writerow((
            linha["posicao_geral"], linha["nome"], linha["dorsal"],
            linha["escalao"] or "",
        ))
    return conteudo.getvalue().encode("utf-8-sig")


def gerar_excel_inscricoes(linhas):
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_namespace = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_namespace = "http://schemas.openxmlformats.org/package/2006/relationships"
    content_namespace = "http://schemas.openxmlformats.org/package/2006/content-types"
    ET.register_namespace("", namespace)
    ET.register_namespace("r", rel_namespace)

    cabecalhos = [
        "N.º aluno", "Nome", "Género", "Data de nascimento", "Turma",
        "Ano letivo", "Prova", "Data da prova", "Local", "Dorsal",
        "Escalão", "Estado", "Desporto Adaptado",
    ]
    campos = [
        "numero_aluno", "aluno", "genero", "data_nascimento", "turma",
        "ano_letivo", "prova", "data_prova", "local", "dorsal",
        "escalao", "estado", "indicador_da",
    ]
    folha = ET.Element(f"{{{namespace}}}worksheet")
    vistas = ET.SubElement(folha, f"{{{namespace}}}sheetViews")
    vista = ET.SubElement(vistas, f"{{{namespace}}}sheetView", {"workbookViewId": "0"})
    ET.SubElement(vista, f"{{{namespace}}}pane", {
        "ySplit": "1", "topLeftCell": "A2",
        "activePane": "bottomLeft", "state": "frozen",
    })
    dados = ET.SubElement(folha, f"{{{namespace}}}sheetData")
    for numero_linha, valores in enumerate(
        [cabecalhos] + [
            [
                ("Sim" if linha[campo] else "Não")
                if campo == "indicador_da" else
                ("" if linha.get(campo) is None else str(linha[campo]))
                for campo in campos
            ]
            for linha in linhas
        ],
        1,
    ):
        linha_xml = ET.SubElement(
            dados, f"{{{namespace}}}row", {"r": str(numero_linha)}
        )
        for indice, valor in enumerate(valores):
            celula = ET.SubElement(linha_xml, f"{{{namespace}}}c", {
                "r": f"{chr(ord('A') + indice)}{numero_linha}",
                "t": "inlineStr",
            })
            texto = ET.SubElement(
                ET.SubElement(celula, f"{{{namespace}}}is"),
                f"{{{namespace}}}t",
            )
            texto.set(f"{{http://www.w3.org/XML/1998/namespace}}space", "preserve")
            texto.text = valor
    ET.SubElement(folha, f"{{{namespace}}}autoFilter", {
        "ref": f"A1:M{len(linhas) + 1}",
    })

    tipos = ET.Element(f"{{{content_namespace}}}Types")
    ET.SubElement(tipos, f"{{{content_namespace}}}Default", {
        "Extension": "rels",
        "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
    })
    ET.SubElement(tipos, f"{{{content_namespace}}}Default", {
        "Extension": "xml", "ContentType": "application/xml",
    })
    ET.SubElement(tipos, f"{{{content_namespace}}}Override", {
        "PartName": "/xl/workbook.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
    })
    ET.SubElement(tipos, f"{{{content_namespace}}}Override", {
        "PartName": "/xl/worksheets/sheet1.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
    })

    rels = ET.Element(f"{{{package_namespace}}}Relationships")
    ET.SubElement(rels, f"{{{package_namespace}}}Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
        "Target": "xl/workbook.xml",
    })
    livro = ET.Element(f"{{{namespace}}}workbook")
    folhas = ET.SubElement(livro, f"{{{namespace}}}sheets")
    ET.SubElement(folhas, f"{{{namespace}}}sheet", {
        "name": "Inscricoes", "sheetId": "1",
        f"{{{rel_namespace}}}id": "rId1",
    })
    rels_livro = ET.Element(f"{{{package_namespace}}}Relationships")
    ET.SubElement(rels_livro, f"{{{package_namespace}}}Relationship", {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
        "Target": "worksheets/sheet1.xml",
    })

    ficheiro_excel = io.BytesIO()
    with zipfile.ZipFile(ficheiro_excel, "w", zipfile.ZIP_DEFLATED) as arquivo:
        partes = {
            "[Content_Types].xml": tipos,
            "_rels/.rels": rels,
            "xl/workbook.xml": livro,
            "xl/_rels/workbook.xml.rels": rels_livro,
            "xl/worksheets/sheet1.xml": folha,
        }
        for nome, elemento in partes.items():
            arquivo.writestr(
                nome, ET.tostring(elemento, encoding="utf-8", xml_declaration=True)
            )
    return ficheiro_excel.getvalue()


def gerar_pdf_classificacao(linhas):
    buffer = io.BytesIO()
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloClassificacao", parent=estilos["Title"],
        textColor=colors.HexColor(VERDE_ESCURO), alignment=TA_CENTER,
        spaceAfter=6,
    )
    subtitulo = ParagraphStyle(
        "SubtituloClassificacao", parent=estilos["Normal"],
        textColor=colors.HexColor("#637168"), alignment=TA_CENTER,
        spaceAfter=18,
    )
    celula = ParagraphStyle(
        "CelulaClassificacao", parent=estilos["BodyText"], fontSize=9,
        leading=12,
    )
    cabecalho = ParagraphStyle(
        "CabecalhoClassificacao", parent=celula, textColor=colors.white,
        fontName="Helvetica-Bold",
    )

    documento = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), rightMargin=36, leftMargin=36,
        topMargin=36, bottomMargin=36, title="Classificação geral",
        author=APP_TITLE,
    )
    dados = [[
        Paragraph("Posição", cabecalho),
        Paragraph("Nome", cabecalho),
        Paragraph("Dorsal", cabecalho),
        Paragraph("Escalão", cabecalho),
    ]]
    for linha in linhas:
        dados.append([
            Paragraph(html.escape(str(linha["posicao_geral"])), celula),
            Paragraph(html.escape(str(linha["nome"])), celula),
            Paragraph(html.escape(str(linha["dorsal"])), celula),
            Paragraph(html.escape(str(linha["escalao"] or "-")), celula),
        ])

    tabela = Table(dados, colWidths=(62, 390, 72, 210), repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(VERDE_ESCURO)),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F0F6F1")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7E2DA")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    documento.build([
        Paragraph("Classificação Geral", titulo),
        Paragraph(html.escape(APP_TITLE), subtitulo),
        tabela,
        Spacer(1, 12),
        Paragraph(f"Gerado em {date.today():%d/%m/%Y} · "
                  f"{len(linhas)} participantes", estilos["Normal"]),
    ])
    return buffer.getvalue()


async def _guardar_com_picker(page, picker, nome, extensao, conteudo,
                              titulo, mensagem):
    caminho = await picker.save_file(
        dialog_title=titulo,
        file_name=nome,
        file_type=ft.FilePickerFileType.CUSTOM,
        allowed_extensions=[extensao],
        src_bytes=conteudo,
    )
    if caminho:
        mensagem.value = f"Ficheiro guardado em: {caminho}"
        mensagem.color = VERDE
    else:
        mensagem.value = "Exportação cancelada."
        mensagem.color = ft.Colors.GREY_700
    page.update()


def login_view(page: ft.Page, on_ok):
    erro = ft.Text("", color=VERMELHO, text_align=ft.TextAlign.CENTER)
    padding_cartao = 24 if (page.width or 1300) < 600 else 36
    largura_cartao = max(240, min(440, (page.width or 1300) - 24))
    largura_campo = max(160, min(340, largura_cartao - padding_cartao * 2))
    user = ft.TextField(label="Utilizador", width=largura_campo, autofocus=True)
    pwd = ft.TextField(label="Palavra-passe", password=True, can_reveal_password=True, width=largura_campo)

    def entrar(e):
        try:
            u = query("""SELECT u.id, u.nome, u.username, u.password_hash, u.ativo
                         FROM utilizadores u WHERE u.username=%s""",
                      ((user.value or "").strip(),), one=True)
        except MySQLError:
            erro.value = "Não foi possível ligar à base de dados. Inicie o MySQL/MariaDB."
            page.update()
            return
        if not u or not verificar(pwd.value or "", u["password_hash"]):
            erro.value = "Credenciais inválidas."
            page.update(); return
        if not u["ativo"]:
            erro.value = "Conta desativada."
            page.update(); return
        perfis = [r["nome"] for r in query(
            "SELECT p.nome FROM utilizador_perfil up JOIN perfis p ON p.id=up.perfil_id "
            "WHERE up.utilizador_id=%s", (u["id"],))]
        S["user"] = {"id": u["id"], "nome": u["nome"], "username": u["username"], "perfis": perfis}
        on_ok()

    pwd.on_submit = entrar

    page.clean()
    page.bgcolor = FUNDO
    page.padding = 12
    login_button = ft.Button(
        "Iniciar sessão", icon=ft.Icons.LOGIN, on_click=entrar,
        width=largura_campo, height=48,
        style=ft.ButtonStyle(
            bgcolor=VERDE, color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=12),
        ),
    )
    cartao = ft.Container(
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
                user, pwd, erro, login_button,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14,
        ),
        width=largura_cartao,
        padding=padding_cartao,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, "#E2E9E4"),
        border_radius=22,
    )
    page.add(ft.Column([cartao],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    ))

    def redimensionar_login(e):
        mobile = (page.width or 1300) < 600
        cartao.padding = 24 if mobile else 36
        cartao.width = max(240, min(440, (page.width or 1300) - 24))
        campo_width = max(160, cartao.width - cartao.padding * 2)
        user.width = pwd.width = login_button.width = campo_width
        page.update()

    page.on_resized = redimensionar_login


def home_view(page: ft.Page, on_logout):
    mobile = (page.width or 1300) < 760
    provas = query("SELECT id, nome, data, ano, estado FROM provas ORDER BY ano DESC, id DESC")
    if not S["prova_id"] and provas:
        S["prova_id"] = provas[0]["id"]

    prova_dd = ft.Dropdown(
        label="Prova",
        width=_responsive_width(page, 390),
        options=[ft.dropdown.Option(str(p["id"]), _etiqueta_prova(p)) for p in provas],
        value=str(S["prova_id"]) if S["prova_id"] else None,
    )

    def escolher_prova(e):
        S["prova_id"] = int(prova_dd.value)
        corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
        page.update()

    prova_dd.on_select = escolher_prova

    corpo = ft.Container(expand=True)

    def atualizar_provas():
        provas_atualizadas = query(
            "SELECT id, nome, data, ano, estado FROM provas ORDER BY ano DESC, id DESC"
        )
        ids_provas = {p["id"] for p in provas_atualizadas}
        selecao_alterada = S["prova_id"] not in ids_provas
        if selecao_alterada:
            S["prova_id"] = provas_atualizadas[0]["id"] if provas_atualizadas else None
        prova_dd.options = [
            ft.dropdown.Option(str(p["id"]), _etiqueta_prova(p))
            for p in provas_atualizadas
        ]
        prova_dd.value = str(S["prova_id"]) if S["prova_id"] else None
        if selecao_alterada:
            corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
        page.update()

    def escolher_secao(e):
        S["_secao"] = e.control.value if mobile else e.control.data
        corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
        painel_menu.content = criar_menu()
        page.update()

    opcoes_menu = [
        (ft.Icons.SETTINGS, "Configurações", "config"),
        (ft.Icons.EDIT_NOTE, "Inscrições", "inscricoes"),
        (ft.Icons.PLAY_ARROW, "Partida", "partida"),
        (ft.Icons.FLAG, "Meta", "meta"),
        (ft.Icons.LEADERBOARD, "Classificações", "classificacoes"),
        (ft.Icons.DESCRIPTION, "Relatórios", "relatorios"),
        (ft.Icons.PEOPLE, "Responsáveis", "responsaveis"),
    ]
    if "Aluno" in S["user"]["perfis"]:
        opcoes_menu = [(ft.Icons.PERSON, "Os meus resultados", "aluno")]
    opcoes_habilitadas = [opcao for opcao in opcoes_menu if pode(opcao[2])]
    secoes_habilitadas = {opcao[2] for opcao in opcoes_habilitadas}
    if S.get("_secao") not in secoes_habilitadas:
        S["_secao"] = opcoes_habilitadas[0][2] if opcoes_habilitadas else None

    def item(icon, label, secao):
        selecionado = S["_secao"] == secao
        cor = VERDE_ESCURO if selecionado else TEXTO
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, color=VERDE if selecionado else ft.Colors.GREY_600,
                                        size=20),
                        width=30,
                        height=30,
                        alignment=ft.Alignment(0, 0),
                        border_radius=10,
                        bgcolor=VERDE_CLARO if selecionado else "#F4F7F5",
                    ),
                    ft.Text(label, color=cor, weight=ft.FontWeight.W_600
                            if selecionado else ft.FontWeight.NORMAL,
                            size=14),
                ],
                spacing=12,
            ),
            data=secao,
            on_click=escolher_secao,
            padding=ft.Padding(10, 12, 10, 12),
            border_radius=14,
            bgcolor=VERDE_CLARO if selecionado else "#F9FBF9",
            border=ft.Border.all(1, "#EAF2EC") if selecionado else None,
        )

    def criar_menu():
        controlos = [
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Text(S["user"]["nome"][:1].upper(),
                                        color=ft.Colors.WHITE,
                                        weight=ft.FontWeight.BOLD,
                                        size=18),
                        width=42,
                        height=42,
                        alignment=ft.Alignment(0, 0),
                        bgcolor=VERDE,
                        border_radius=14,
                    ),
                    ft.Column([
                        ft.Text(S["user"]["nome"], weight=ft.FontWeight.BOLD,
                                color=TEXTO, size=14),
                        ft.Text(", ".join(S["user"]["perfis"]), size=11,
                                color=TEXTO_MUTO),
                    ], spacing=2, expand=True),
                ], spacing=12),
                padding=ft.Padding(10, 12, 10, 12),
                bgcolor="#F4F9F5",
                border=ft.Border.all(1, "#E6F0E8"),
                border_radius=16,
                margin=ft.Margin.only(bottom=10),
            ),
            ft.Container(
                content=ft.Text("MENU", size=11, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREY_600),
                padding=ft.Padding(8, 0, 8, 8),
            ),
        ]
        itens_menu = [
            ft.Container(
                content=item(icon, label, secao),
                margin=ft.Margin.only(bottom=4),
            )
            for icon, label, secao in opcoes_habilitadas
        ]
        controlos.extend(itens_menu)
        if not opcoes_habilitadas:
            controlos.append(ft.Text("Não existem opções habilitadas para esta conta."))
        controlos.extend([
            ft.Container(expand=True),
            ft.Divider(),
            ft.Container(
                content=ft.TextButton(
                    "Terminar sessão", icon=ft.Icons.LOGOUT,
                    on_click=lambda e: on_logout(),
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
                alignment=ft.Alignment(0, 0),
                padding=ft.Padding(0, 4, 0, 0),
            ),
        ])
        return ft.Column(controlos, spacing=5, expand=True)

    secao_dd = ft.Dropdown(
        label="Secção",
        width=_responsive_width(page, 390),
        options=[
            ft.dropdown.Option(secao, label)
            for _, label, secao in opcoes_habilitadas
        ],
        value=S["_secao"],
        on_select=escolher_secao,
    )

    corpo.content = _corpo_atual(page, on_logout, atualizar_provas)
    painel_menu = ft.Container(
        content=criar_menu(),
        width=270,
        padding=18,
        bgcolor=CARD,
        border=ft.Border.all(1, BORDA),
        border_radius=20,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        shadow=ft.BoxShadow(
            blur_radius=18,
            color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
            spread_radius=0,
        ),
    )

    page.clean()
    page.bgcolor = FUNDO
    painel_corpo = ft.Container(
        content=corpo,
        padding=12 if mobile else 24,
        bgcolor=CARD,
        border=ft.Border.all(1, BORDA),
        border_radius=20,
        expand=True,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        shadow=ft.BoxShadow(
            blur_radius=18,
            color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
            spread_radius=0,
        ),
    )
    cabecalho = ft.Container(
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
                            color=TEXTO_MUTO),
                ], spacing=1),
            ], spacing=12),
            ft.Container(content=prova_dd, width=_responsive_width(page, 390)),
        ], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding(12 if mobile else 22, 12, 12 if mobile else 22, 12),
        bgcolor=CARD,
        border=ft.Border.all(1, BORDA),
        border_radius=20,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        shadow=ft.BoxShadow(
            blur_radius=16,
            color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
            offset=ft.Offset(0, 3),
            spread_radius=0,
        ),
    )
    logout_mobile = ft.TextButton(
        "Terminar sessão", icon=ft.Icons.LOGOUT, on_click=lambda e: on_logout(),
        style=ft.ButtonStyle(color=VERMELHO),
    )
    navegacao_mobile = ft.Container(
        content=ft.Row(
            [secao_dd, logout_mobile],
            wrap=True,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(12, 8, 12, 8),
        bgcolor=CARD,
        border=ft.Border.all(1, BORDA),
        border_radius=20,
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
        shadow=ft.BoxShadow(
            blur_radius=12,
            color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
            offset=ft.Offset(0, 2),
            spread_radius=0,
        ),
    )
    corpo_layout = (
        ft.Column([navegacao_mobile, painel_corpo], expand=True, spacing=10)
        if mobile else
        ft.Row([painel_menu, painel_corpo], expand=True, spacing=16,
               vertical_alignment=ft.CrossAxisAlignment.STRETCH)
    )
    page.padding = 8 if mobile else 20
    page.add(ft.Column([
        cabecalho,
        corpo_layout,
    ], expand=True, spacing=10 if mobile else 16))

    def redimensionar(e):
        layout_mobile = (page.width or 1300) < 760
        if layout_mobile != mobile:
            home_view(page, on_logout)

    page.on_resized = redimensionar


def _corpo_atual(page, on_logout, on_prova_apagada=None):
    secao = S.get("_secao", "config")
    if not secao or not pode(secao):
        return ft.Text("Não existem opções habilitadas para esta conta.")
    if secao == "config":
        return config_view(page, on_prova_apagada)
    if secao == "inscricoes":  return inscricoes_view(page)
    if secao == "partida":     return partida_view(page)
    if secao == "meta":        return meta_view(page)
    if secao == "classificacoes": return classificacoes_view(page)
    if secao == "relatorios":  return relatorios_view(page)
    if secao == "responsaveis": return responsaveis_view(page)
    if secao == "aluno": return aluno_view(page)
    return ft.Text("?")

def aluno_view(page):
    pid = S["prova_id"]
    resultados = []
    if pid:
        resultados = query("""SELECT a.nome, t.codigo AS turma, e.nome AS escalao,
                                     i.dorsal, ci.posicao_geral, ci.posicao_escalao,
                                     ci.posicao_genero, ci.apurado
                              FROM alunos a
                              JOIN turmas t ON t.id=a.turma_id
                              JOIN inscricoes i ON i.aluno_id=a.id
                              JOIN classificacoes_individuais ci
                                ON ci.inscricao_id=i.id AND ci.prova_id=i.prova_id
                              LEFT JOIN escaloes e ON e.id=i.escalao_id
                              WHERE a.numero_aluno=%s AND i.prova_id=%s
                              ORDER BY ci.posicao_geral""",
                            (S["user"]["username"], pid))
    conteudo = [
        ft.Text("Os meus resultados", size=20, weight=ft.FontWeight.BOLD),
    ]
    if not pid:
        conteudo.append(ft.Text("Ainda não existem provas disponíveis."))
    elif not resultados:
        conteudo.append(ft.Text("Ainda não existem classificações para esta prova."))
    else:
        for resultado in resultados:
            conteudo.append(ft.ListTile(
                title=ft.Text(resultado["nome"]),
                subtitle=ft.Text(
                    f"Turma {resultado['turma']} · {resultado['escalao'] or '-'} · "
                    f"Dorsal {resultado['dorsal'] or '-'}"
                ),
                trailing=ft.Column([
                    ft.Text(f"{resultado['posicao_geral']}º lugar"),
                    ft.Text(f"Escalão: {resultado['posicao_escalao']}º · "
                            f"Género: {resultado['posicao_genero']}º"),
                ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.END),
            ))
            if resultado["apurado"]:
                conteudo.append(ft.Text("Apurado para a fase seguinte", color=VERDE))

    pdf_info = ft.Text("", size=12)

    picker = None
    if pid and not page.web:
        picker = S.get("_aluno_pdf_picker")
        if picker is None:
            picker = ft.FilePicker()
            page.services.append(picker)
            S["_aluno_pdf_picker"] = picker

    async def exportar_classificacoes(e):
        linhas = query("""SELECT ci.posicao_geral, a.nome, i.dorsal, e.nome AS escalao
                          FROM classificacoes_individuais ci
                          JOIN inscricoes i ON i.id=ci.inscricao_id
                          JOIN alunos a ON a.id=i.aluno_id
                          LEFT JOIN escaloes e ON e.id=i.escalao_id
                          WHERE ci.prova_id=%s ORDER BY ci.posicao_geral""", (pid,))
        if not linhas:
            pdf_info.value = "Ainda não existem classificações para esta prova."
            pdf_info.color = ft.Colors.GREY_700
            page.update()
            return

        nome = f"classificacao_geral_prova{pid}.pdf"
        conteudo_pdf = gerar_pdf_classificacao(linhas)
        if page.web:
            dados = base64.b64encode(conteudo_pdf).decode("ascii")
            page.launch_url(f"data:application/pdf;base64,{dados}")
            pdf_info.value = "PDF aberto no navegador. Utilize a opção Guardar para o guardar."
            pdf_info.color = VERDE
            page.update()
            return

        await _guardar_com_picker(
            page, picker, nome, "pdf", conteudo_pdf,
            "Guardar classificações", pdf_info,
        )

    informacoes = ft.Column([
        ft.Text("Informações gerais da prova", size=20, weight=ft.FontWeight.BOLD),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.EVENT, color=VERDE),
            title=ft.Text("Data da prova"),
            subtitle=ft.Text("18-11-2026"),
        ),
        ft.Text("Consulte ou transfira o PDF com as classificações gerais."),
        ft.Button(
            "Transferir classificações (PDF)",
            icon=ft.Icons.PICTURE_AS_PDF,
            on_click=exportar_classificacoes,
            disabled=not pid,
        ),
        pdf_info,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

    return ft.Tabs(
        content=ft.Column([
            ft.TabBar(tabs=[
                ft.Tab(label="Os meus resultados"),
                ft.Tab(label="Informações gerais da prova"),
            ]),
            ft.TabBarView(controls=[
                ft.Column(conteudo, scroll=ft.ScrollMode.AUTO, expand=True),
                informacoes,
            ], expand=True),
        ], expand=True),
        length=2,
        selected_index=0,
        expand=True,
    )

def config_view(page, on_prova_apagada=None):
    lista = ft.Column()
    nome = ft.TextField(label="Nome da prova", width=_responsive_width(page, 280))
    local = ft.TextField(label="Local", width=_responsive_width(page, 220))
    data_ = ft.TextField(label="Data (AAAA-MM-DD)", width=_responsive_width(page, 160))
    estado = ft.Dropdown(label="Estado", width=_responsive_width(page, 140), value="Planeada",
                         options=[ft.dropdown.Option(x) for x in ("Planeada", "Em curso", "Terminada")])

    def carregar():
        lista.controls.clear()
        for p in query("SELECT * FROM provas ORDER BY ano DESC, id DESC"):
            nome_texto = str(p["nome"]).strip() if p.get("nome") is not None else ""
            data_texto = str(p["data"]).strip() if p.get("data") is not None else "-"
            local_texto = str(p["local"]).strip() if p.get("local") is not None else "-"
            estado_texto = str(p["estado"]).strip() if p.get("estado") is not None else "-"
            data_texto = data_texto or "-"
            local_texto = local_texto or "-"
            estado_texto = estado_texto or "-"
            lista.controls.append(
                ft.Container(
                    content=ft.ListTile(
                        leading=ft.Icon(ft.Icons.EVENT, color=VERDE),
                        title=ft.Row([
                            ft.Text(nome_texto or "Sem nome", weight=ft.FontWeight.W_500, size=14),
                            ft.Text(
                                f" | {data_texto} | {local_texto} | {estado_texto}",
                                weight=ft.FontWeight.NORMAL,
                                size=13,
                                color=TEXTO_MUTO,
                            ),
                        ], spacing=8, wrap=True, alignment=ft.MainAxisAlignment.START),
                        trailing=ft.Row([
                            ft.IconButton(ft.Icons.EDIT, data=p["id"], on_click=editar,
                                          tooltip="Editar prova"),
                            ft.IconButton(ft.Icons.DELETE, data=p["id"],
                                          on_click=confirmar_apagamento,
                                          icon_color=VERMELHO, tooltip="Apagar prova"),
                        ], tight=True, spacing=0),
                    ),
                    padding=ft.Padding(0, 0, 0, 0),
                    border=ft.Border.all(1, BORDA),
                    border_radius=16,
                    bgcolor="#F9FBF9",
                    margin=ft.Margin.only(bottom=8),
                )
            )
        page.update()

    def confirmar_apagamento(e):
        prova_id = e.control.data
        prova = query("SELECT nome, ano, data FROM provas WHERE id=%s",
                      (prova_id,), one=True)
        if not prova:
            carregar()
            return

        def apagar(e):
            execute("DELETE FROM provas WHERE id=%s", (prova_id,))
            if S.get("_edit_prova") == prova_id:
                S.pop("_edit_prova", None)
                nome.value = local.value = data_.value = ""
                estado.value = "Planeada"
            page.close(dialog)
            carregar()
            if on_prova_apagada:
                on_prova_apagada()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Apagar prova?"),
            content=ft.Text(
                f"Tem a certeza de que pretende apagar «{prova['nome']}» "
                f"({_etiqueta_prova(prova)})? As inscrições, chegadas, ocorrências e "
                "classificações associadas também serão apagadas. Esta ação "
                "não pode ser desfeita."
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda e: page.close(dialog)),
                ft.TextButton(
                    "Apagar prova", on_click=apagar,
                    style=ft.ButtonStyle(color=VERMELHO),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.open(dialog)

    def editar(e):
        p = query("SELECT * FROM provas WHERE id=%s", (e.control.data,), one=True)
        nome.value = p["nome"]
        local.value = p["local"] or ""
        data_.value = str(p["data"]) if p["data"] else ""
        estado.value = p["estado"]
        S["_edit_prova"] = p["id"]
        page.update()

    def guardar(e):
        nome_limpo = nome.value.strip()
        local_limpo = local.value.strip()
        if not nome_limpo:
            return
        d = data_.value.strip() or None
        ano = _ano_a_partir_data(d) or date.today().year
        if S.get("_edit_prova"):
            execute("UPDATE provas SET nome=%s, ano=%s, data=%s, local=%s, estado=%s WHERE id=%s",
                    (nome_limpo, ano, d, local_limpo or None,
                     estado.value, S["_edit_prova"]))
            S.pop("_edit_prova", None)
        else:
            execute("INSERT INTO provas (nome, ano, data, local, estado) VALUES (%s,%s,%s,%s,%s)",
                    (nome_limpo, ano, d, local_limpo or None, estado.value))
        nome.value = local.value = data_.value = ""
        carregar()

    def nova(e):
        S.pop("_edit_prova", None)
        nome.value = local.value = data_.value = ""
        estado.value = "Planeada"
        page.update()

    carregar()
    return ft.Column([
        ft.Text("Provas", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([nome, local, data_, estado,
                ft.Button("Guardar", on_click=guardar),
                ft.OutlinedButton("Limpar", on_click=nova)], wrap=True, spacing=8),
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)


def inscricoes_view(page):
    if not S["prova_id"]:
        return ft.Text("Cria primeiro uma prova em Configurações.")
    pid = S["prova_id"]
    admin = "Administrador" in S["user"]["perfis"]

    alunos_dd = ft.Dropdown(label="Aluno", width=_responsive_width(page, 380))
    da = ft.Checkbox(label="DA (Desporto Adaptado)")
    estado = ft.Dropdown(label="Estado", width=_responsive_width(page, 160), value="Inscrito",
                         options=[ft.dropdown.Option(x) for x in
                                  ("Inscrito", "Participante", "Organizacao")])
    erro = ft.Text("", color=VERMELHO, size=12)
    exportacao_info = ft.Text("", size=12)
    lista = ft.Column()
    novo_aluno = ft.Switch(label="Registar novo aluno", value=False) if admin else None
    numero_novo = ft.TextField(
        label="Nº aluno (5 algarismos)", max_length=5,
        width=_responsive_width(page, 200),
    )
    nome_novo = ft.TextField(label="Nome completo", width=_responsive_width(page, 280))
    genero_novo = ft.Dropdown(
        label="Género", width=_responsive_width(page, 160),
        options=[
            ft.dropdown.Option("M", "Masculino"),
            ft.dropdown.Option("F", "Feminino"),
        ],
    )
    nascimento_novo = ft.TextField(
        label="Data de nascimento (AAAA-MM-DD)",
        width=_responsive_width(page, 230),
    )
    ano_escolar_novo = ft.Dropdown(
        label="Ano escolar", width=_responsive_width(page, 160),
        options=[
            ft.dropdown.Option(str(ano), f"{ano}.º ano")
            for ano in range(5, 13)
        ],
    )
    turma_novo = ft.Dropdown(
        label="Turma", width=_responsive_width(page, 120),
        options=[
            ft.dropdown.Option(chr(letra))
            for letra in range(ord("A"), ord("Z") + 1)
        ],
    )
    campos_novo = ft.Column(
        [ft.Row([numero_novo, nome_novo, genero_novo, nascimento_novo,
                 ano_escolar_novo, turma_novo],
                wrap=True, spacing=8)],
        visible=False,
    )

    def carregar():
        alunos_dd.options = [
            ft.dropdown.Option(str(a["id"]), f"{a['numero_aluno']} · {a['nome']} ({a['turma']})")
            for a in query("""SELECT a.id, a.numero_aluno, a.nome, t.codigo AS turma
                              FROM alunos a JOIN turmas t ON t.id=a.turma_id
                              ORDER BY a.nome""")
        ]
        lista.controls.clear()
        for i in query("""SELECT i.id, i.dorsal, i.estado, i.indicador_da, a.nome, a.numero_aluno,
                                 e.nome AS escalao
                          FROM inscricoes i
                          JOIN alunos a ON a.id=i.aluno_id
                          LEFT JOIN escaloes e ON e.id=i.escalao_id
                          WHERE i.prova_id=%s ORDER BY i.dorsal""", (pid,)):
            lista.controls.append(ft.ListTile(
                title=ft.Text(f"#{i['dorsal']} · {i['nome']}"),
                subtitle=ft.Text(f"nº {i['numero_aluno']} · {i['escalao'] or '-'} · {i['estado']}"
                                 f"{' · DA' if i['indicador_da'] else ''}"),
                trailing=ft.IconButton(ft.Icons.DELETE, data=i["id"], on_click=apagar,
                                       icon_color=VERMELHO),
            ))
        page.update()

    picker_excel = None
    if not page.web:
        picker_excel = S.get("_inscricoes_excel_picker")
        if picker_excel is None:
            picker_excel = ft.FilePicker()
            page.services.append(picker_excel)
            S["_inscricoes_excel_picker"] = picker_excel

    async def exportar_excel(e):
        linhas = query("""SELECT a.numero_aluno, a.nome AS aluno, a.genero,
                                 a.data_nascimento, t.codigo AS turma, a.ano_letivo,
                                 p.nome AS prova, p.data AS data_prova, p.local,
                                 i.dorsal, e.nome AS escalao, i.estado,
                                 i.indicador_da
                          FROM inscricoes i
                          JOIN alunos a ON a.id=i.aluno_id
                          JOIN turmas t ON t.id=a.turma_id
                          JOIN provas p ON p.id=i.prova_id
                          LEFT JOIN escaloes e ON e.id=i.escalao_id
                          WHERE i.prova_id=%s
                          ORDER BY i.dorsal, a.nome""", (pid,))
        if not linhas:
            exportacao_info.value = "Não existem alunos inscritos nesta prova."
            exportacao_info.color = ft.Colors.GREY_700
            page.update()
            return

        nome_ficheiro = f"inscritos_prova{pid}.xlsx"
        conteudo = gerar_excel_inscricoes(linhas)
        if page.web:
            dados = base64.b64encode(conteudo).decode("ascii")
            page.launch_url(
                "data:application/vnd.openxmlformats-officedocument."
                f"spreadsheetml.sheet;base64,{dados}"
            )
            exportacao_info.value = "O Excel foi gerado para transferência."
            exportacao_info.color = VERDE
            page.update()
            return

        await _guardar_com_picker(
            page, picker_excel, nome_ficheiro, "xlsx", conteudo,
            "Guardar alunos inscritos", exportacao_info,
        )

    def apagar(e):
        execute("DELETE FROM inscricoes WHERE id=%s", (e.control.data,))
        carregar()

    def alterar_modo_aluno(e):
        alunos_dd.visible = not e.control.value
        campos_novo.visible = e.control.value
        page.update()

    def obter_perfil_aluno():
        return query("SELECT id FROM perfis WHERE nome='Aluno'", one=True)

    def obter_conta(numero):
        return query("""SELECT u.id, GROUP_CONCAT(p.nome) AS perfis
                        FROM utilizadores u
                        LEFT JOIN utilizador_perfil up ON up.utilizador_id=u.id
                        LEFT JOIN perfis p ON p.id=up.perfil_id
                        WHERE u.username=%s
                        GROUP BY u.id""", (numero,), one=True)

    def conta_e_apenas_aluno(conta):
        return conta is not None and set(
            (conta["perfis"] or "").split(",")
        ) == {"Aluno"}

    def criar_inscricao(aluno_id, genero, nascimento, criar_conta, turma_id=None,
                        numero=None, nome=None, ano_letivo=None):
        prova = query("SELECT ano FROM provas WHERE id=%s", (pid,), one=True)
        idade = prova["ano"] - nascimento.year
        esc = query("""SELECT id FROM escaloes
                       WHERE genero=%s AND idade_minima<=%s AND idade_maxima>=%s""",
                    (genero, idade, idade), one=True)
        dorsal = query(
            "SELECT COALESCE(MAX(dorsal),0)+1 AS n FROM inscricoes WHERE prova_id=%s",
            (pid,), one=True,
        )["n"]
        qr = f"RC{pid}-{dorsal}"
        escalao_id = esc["id"] if esc else None
        statements = []

        if criar_conta:
            perfil = obter_perfil_aluno()
            if not perfil:
                erro.value = "Perfil de aluno inexistente. Execute setup_db.py."
                erro.color = VERMELHO
                page.update()
                return False
            statements.extend([
                (
                    "INSERT INTO utilizadores (nome, username, password_hash, ativo) "
                    "VALUES (%s,%s,%s,TRUE)",
                    (nome, numero, hash_password(numero)),
                ),
                (
                    "INSERT INTO utilizador_perfil (utilizador_id, perfil_id) "
                    "VALUES (LAST_INSERT_ID(),%s)",
                    (perfil["id"],),
                ),
            ])

        if aluno_id is None:
            statements.append((
                "INSERT INTO alunos "
                "(numero_aluno, nome, genero, data_nascimento, turma_id, ano_letivo) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (numero, nome, genero, nascimento, turma_id, ano_letivo),
            ))
            inscricao_sql = """INSERT INTO inscricoes
                               (prova_id, aluno_id, escalao_id, dorsal, qr_code,
                                indicador_da, estado)
                               VALUES (%s,LAST_INSERT_ID(),%s,%s,%s,%s,%s)"""
            inscricao_params = (pid, escalao_id, dorsal, qr, da.value, estado.value)
        else:
            inscricao_sql = """INSERT INTO inscricoes
                               (prova_id, aluno_id, escalao_id, dorsal, qr_code,
                                indicador_da, estado)
                               VALUES (%s,%s,%s,%s,%s,%s,%s)"""
            inscricao_params = (
                pid, aluno_id, escalao_id, dorsal, qr, da.value, estado.value,
            )

        statements.append((inscricao_sql, inscricao_params))
        try:
            execute_transaction(statements)
        except IntegrityError:
            erro.value = (
                "Não foi possível guardar: o aluno já está inscrito, "
                "o número já existe ou já está associado a outra conta."
            )
            erro.color = VERMELHO
            page.update()
            return False
        return True

    def inscrever_novo_aluno():
        numero = (numero_novo.value or "").strip()
        nome = (nome_novo.value or "").strip()
        if not numero.isascii() or not numero.isdigit() or len(numero) != 5:
            erro.value = "O número do aluno tem de conter exatamente 5 algarismos."
            erro.color = VERMELHO
            page.update()
            return
        if not nome or not genero_novo.value or not nascimento_novo.value \
                or not ano_escolar_novo.value or not turma_novo.value:
            erro.value = "Preencha todos os dados do aluno."
            erro.color = VERMELHO
            page.update()
            return
        try:
            nascimento = date.fromisoformat(nascimento_novo.value.strip())
        except ValueError:
            erro.value = "Indique a data de nascimento no formato AAAA-MM-DD."
            erro.color = VERMELHO
            page.update()
            return

        ano_letivo = _ano_letivo_atual()
        codigo_turma = f"{ano_escolar_novo.value}{turma_novo.value}"
        if query(
            "SELECT id FROM alunos WHERE numero_aluno=%s AND ano_letivo=%s",
            (numero, ano_letivo), one=True,
        ):
            erro.value = "Este aluno já está registado nesta turma/ano letivo."
            erro.color = VERMELHO
            page.update()
            return

        conta = obter_conta(numero)
        if conta and not conta_e_apenas_aluno(conta):
            erro.value = "Este número já está associado a uma conta que não é de aluno."
            erro.color = VERMELHO
            page.update()
            return

        turma_id = execute(
            "INSERT INTO turmas (codigo, nome, ano_letivo) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)",
            (codigo_turma, f"{ano_escolar_novo.value}.º {turma_novo.value}", ano_letivo),
        )
        criado = criar_inscricao(
            None, genero_novo.value, nascimento, not conta,
            turma_id=turma_id, numero=numero, nome=nome,
            ano_letivo=ano_letivo,
        )
        if not criado:
            return
        erro.value = (
            f"Aluno inscrito. Conta criada — utilizador e palavra-passe: {numero}."
            if not conta else
            f"Aluno inscrito. Já existe uma conta de aluno para o número {numero}."
        )
        erro.color = VERDE
        numero_novo.value = nome_novo.value = nascimento_novo.value = ""
        genero_novo.value = ano_escolar_novo.value = turma_novo.value = None
        novo_aluno.value = False
        alunos_dd.visible = True
        campos_novo.visible = False
        carregar()

    def inscrever(e):
        if novo_aluno and novo_aluno.value:
            inscrever_novo_aluno()
            return
        if not alunos_dd.value:
            erro.value = "Selecione um aluno."
            erro.color = VERMELHO
            page.update()
            return
        aluno_id = int(alunos_dd.value)
        aluno = query(
            "SELECT numero_aluno, nome, data_nascimento, genero FROM alunos WHERE id=%s",
            (aluno_id,), one=True,
        )
        conta = obter_conta(aluno["numero_aluno"]) if admin else None
        if conta and not conta_e_apenas_aluno(conta):
            erro.value = "Este número já está associado a uma conta que não é de aluno."
            erro.color = VERMELHO
            page.update()
            return
        criar_conta = admin and conta is None
        if criar_conta and (
            not aluno["numero_aluno"].isascii()
            or not aluno["numero_aluno"].isdigit()
            or len(aluno["numero_aluno"]) != 5
        ):
            erro.value = "O número do aluno tem de conter exatamente 5 algarismos."
            erro.color = VERMELHO
            page.update()
            return
        if criar_inscricao(
            aluno_id, aluno["genero"], aluno["data_nascimento"], criar_conta,
            numero=aluno["numero_aluno"], nome=aluno["nome"],
        ):
            erro.value = (
                f"Inscrição guardada. Conta criada — utilizador e palavra-passe: "
                f"{aluno['numero_aluno']}."
                if criar_conta else "Inscrição guardada."
            )
            erro.color = VERDE
        carregar()

    if novo_aluno:
        novo_aluno.on_change = alterar_modo_aluno

    carregar()
    return ft.Column([
        ft.Text("Inscrições", size=20, weight=ft.FontWeight.BOLD),
        ft.Row(
            ([novo_aluno] if novo_aluno else []) + [alunos_dd, da, estado],
            wrap=True, spacing=8,
        ),
        campos_novo,
        erro,
        ft.Row([
            ft.Button("Guardar inscrição", on_click=inscrever),
            ft.OutlinedButton(
                "Transferir Excel", icon=ft.Icons.DOWNLOAD,
                on_click=exportar_excel,
            ),
        ],
               wrap=True, spacing=8),
        exportacao_info,
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def partida_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Text("Sem prova.")
    txt = ft.TextField(label="Nº dorsal ou QR (RCx-n)", width=_responsive_width(page, 280))
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

    def marcar(e):
        execute("UPDATE inscricoes SET estado='Participante' WHERE id=%s", (e.control.data,))
        carregar()

    def por_texto(e):
        v = (txt.value or "").strip()
        if not v:
            return
        row = query("SELECT id FROM inscricoes WHERE prova_id=%s AND (qr_code=%s OR dorsal=%s)",
                    (pid, v, v if v.isdigit() else -1), one=True)
        if row:
            execute("UPDATE inscricoes SET estado='Participante' WHERE id=%s", (row["id"],))
            txt.value = ""; carregar()

    def dar_partida(e):
        if not query("SELECT id FROM partidas WHERE prova_id=%s", (pid,), one=True):
            execute("INSERT INTO partidas (prova_id, hora_inicio) VALUES (%s, NOW())", (pid,))
        carregar()

    carregar()
    return ft.Column([
        ft.Text("Partida", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([txt, ft.Button("Entregar", on_click=por_texto),
                ft.Button("Dar partida", on_click=dar_partida,
                                  bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE)],
               wrap=True, spacing=8),
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def meta_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Text("Sem prova.")
    txt = ft.TextField(label="QR / dorsal", width=_responsive_width(page, 260), autofocus=True)
    motivo = ft.TextField(
        label="Motivo da desclassificação",
        width=_responsive_width(page, 500),
        multiline=True,
        min_lines=3,
        max_lines=5,
        max_length=1000,
    )
    formulario_desclassificacao = ft.Column(visible=False, spacing=8)
    lista = ft.Column()

    def carregar():
        lista.controls.clear()
        for c in query("""SELECT c.ordem, a.nome, i.dorsal
                          FROM chegadas c
                          JOIN inscricoes i ON i.id=c.inscricao_id
                          JOIN alunos a ON a.id=i.aluno_id
                          WHERE c.prova_id=%s ORDER BY c.ordem""", (pid,)):
            lista.controls.append(ft.ListTile(
                leading=ft.CircleAvatar(content=ft.Text(str(c["ordem"]))),
                title=ft.Text(f"{c['nome']} (#{c['dorsal']})"),
            ))
        page.update()

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

    def ocorrencia(tipo, motivo_texto=None):
        v = (txt.value or "").strip()
        if not v:
            return False
        row = query("SELECT id FROM inscricoes WHERE prova_id=%s AND (qr_code=%s OR dorsal=%s)",
                    (pid, v, v if v.isdigit() else -1), one=True)
        if not row:
            return False
        execute("""INSERT IGNORE INTO ocorrencias (prova_id, inscricao_id, tipo, motivo)
                   VALUES (%s,%s,%s,%s)""",
                (pid, row["id"], tipo, motivo_texto or None))
        txt.value = ""
        carregar()
        return True

    def abrir_desclassificacao(e):
        formulario_desclassificacao.visible = True
        page.update()

    def confirmar_desclassificacao(e):
        texto = (motivo.value or "").strip()
        if ocorrencia("Desclassificacao", texto):
            motivo.value = ""
            formulario_desclassificacao.visible = False
            page.update()

    def cancelar_desclassificacao(e):
        motivo.value = ""
        formulario_desclassificacao.visible = False
        page.update()

    formulario_desclassificacao.controls.extend([
        motivo,
        ft.Row([
            ft.Button(
                "Confirmar desclassificação",
                on_click=confirmar_desclassificacao,
                bgcolor=VERMELHO,
                color=ft.Colors.WHITE,
            ),
            ft.TextButton("Cancelar", on_click=cancelar_desclassificacao),
        ], spacing=8, wrap=True),
    ])

    carregar()
    return ft.Column([
        ft.Text("Meta", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([txt,
                ft.Button("Chegada", on_click=chegada),
                ft.OutlinedButton("Desistência", icon=ft.Icons.EXIT_TO_APP,
                                  on_click=lambda e: ocorrencia("Desistencia"),
                                  style=ft.ButtonStyle(color=VERMELHO)),
                ft.OutlinedButton("Desclassificação", icon=ft.Icons.BLOCK,
                                  on_click=abrir_desclassificacao,
                                  style=ft.ButtonStyle(color=VERMELHO))],
               wrap=True, spacing=8),
        formulario_desclassificacao,
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def classificacoes_view(page):
    pid = S["prova_id"]
    if not pid:
        return ft.Text("Sem prova.")
    tab = ft.Column()

    def calcular():
        execute("DELETE FROM classificacoes_individuais WHERE prova_id=%s", (pid,))
        execute("DELETE FROM classificacoes_coletivas WHERE prova_id=%s", (pid,))
        rows = query("""SELECT c.ordem, i.id AS inscricao_id, i.escalao_id, i.indicador_da,
                               a.genero, a.turma_id
                        FROM chegadas c
                        JOIN inscricoes i ON i.id=c.inscricao_id
                        JOIN alunos a ON a.id=i.aluno_id
                        WHERE c.prova_id=%s
                          AND NOT EXISTS (SELECT 1 FROM ocorrencias o
                                          WHERE o.prova_id=c.prova_id AND o.inscricao_id=i.id)
                        ORDER BY c.ordem""", (pid,))
        pos_geral = 0
        pos_esc, pos_gen, pos_da = {}, {}, {}
        for r in rows:
            pos_geral += 1
            pos_esc[r["escalao_id"]] = pos_esc.get(r["escalao_id"], 0) + 1
            pos_gen[(r["escalao_id"], r["genero"])] = pos_gen.get((r["escalao_id"], r["genero"]), 0) + 1
            if r["indicador_da"]:
                pos_da[r["escalao_id"]] = pos_da.get(r["escalao_id"], 0) + 1
            execute("""INSERT INTO classificacoes_individuais
                       (prova_id, inscricao_id, posicao_geral, posicao_escalao,
                        posicao_genero, posicao_da, apurado)
                       VALUES (%s,%s,%s,%s,%s,%s,0)""",
                    (pid, r["inscricao_id"], pos_geral,
                     pos_esc[r["escalao_id"]],
                     pos_gen[(r["escalao_id"], r["genero"])],
                     pos_da.get(r["escalao_id"]) if r["indicador_da"] else None))
        for regra in query("SELECT escalao_id, indicador_da, num_apurados FROM regras_apuramento"):
            if regra["num_apurados"] <= 0:
                continue
            q = """SELECT ci.id FROM classificacoes_individuais ci
                   JOIN inscricoes i ON i.id=ci.inscricao_id
                   WHERE ci.prova_id=%s AND i.escalao_id=%s
                     AND i.indicador_da=%s
                   ORDER BY ci.posicao_escalao LIMIT %s"""
            for row in query(q, (pid, regra["escalao_id"], regra["indicador_da"], regra["num_apurados"])):
                execute("UPDATE classificacoes_individuais SET apurado=1 WHERE id=%s", (row["id"],))
        pts = {}
        for r in rows:
            pts.setdefault(r["turma_id"], []).append(r["ordem"])
        for turma_id, ordens in pts.items():
            top4 = sorted(ordens)[:4]
            if len(top4) == 4:
                execute("INSERT INTO classificacoes_coletivas (prova_id, turma_id, pontos) "
                        "VALUES (%s,%s,%s)",
                        (pid, turma_id, sum(top4)))
        for i, r in enumerate(query("SELECT id FROM classificacoes_coletivas "
                                    "WHERE prova_id=%s ORDER BY pontos", (pid,)), 1):
            execute("UPDATE classificacoes_coletivas SET posicao=%s WHERE id=%s", (i, r["id"]))
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
    historico = ft.Column()

    for edicao in query("""SELECT p.nome, p.data, p.ano, COUNT(ci.id) AS participantes,
                                  GROUP_CONCAT(
                                      CASE WHEN ci.posicao_geral <= 3
                                           THEN CONCAT(ci.posicao_geral, 'º ', a.nome)
                                      END
                                      ORDER BY ci.posicao_geral SEPARATOR ' · '
                                  ) AS podio
                           FROM provas p
                           JOIN classificacoes_individuais ci ON ci.prova_id=p.id
                           JOIN inscricoes i ON i.id=ci.inscricao_id
                           JOIN alunos a ON a.id=i.aluno_id
                           WHERE p.ano < (SELECT ano FROM provas WHERE id=%s)
                           GROUP BY p.id, p.nome, p.data, p.ano
                           ORDER BY p.ano DESC, p.id DESC""", (pid,)):
        historico.controls.append(ft.ListTile(
            title=ft.Text(f"{edicao['data'] or edicao['ano']} · {edicao['nome']}"),
            subtitle=ft.Text(
                f"{edicao['participantes']} participantes · "
                f"Pódio: {edicao['podio'] or 'sem classificações'}"
            ),
        ))
    if not historico.controls:
        historico.controls.append(ft.Text(
            "Ainda não existem classificações de anos anteriores."
        ))

    picker = None
    if not page.web:
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
        if page.web:
            tipo = "text/csv" if extensao == "csv" else "application/pdf"
            dados = base64.b64encode(conteudo).decode("ascii")
            page.launch_url(f"data:{tipo};base64,{dados}")
            info.value = "Relatório aberto no navegador. Utilize a opção Guardar para o guardar."
            info.color = VERDE
            page.update()
            return

        await _guardar_com_picker(
            page, picker, nome, extensao, conteudo,
            "Guardar relatório", info,
        )

    async def exportar_csv(e):
        linhas = obter_linhas()
        nome = f"classificacao_geral_prova{pid}.csv"
        await guardar_exportacao(nome, "csv", gerar_csv_classificacao(linhas))

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
        ft.Divider(),
        ft.Text("Histórico de anos anteriores", size=18,
                weight=ft.FontWeight.BOLD),
        historico,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def responsaveis_view(page):
    nome = ft.TextField(label="Nome", width=_responsive_width(page, 200))
    user = ft.TextField(label="Utilizador", width=_responsive_width(page, 160))
    pwd = ft.TextField(label="Palavra-passe", password=True, width=_responsive_width(page, 160))
    perfil_dd = ft.Dropdown(label="Perfil", width=_responsive_width(page, 200))
    erro = ft.Text("", color=VERMELHO, size=12)
    lista = ft.Column()

    def carregar():
        perfis = query("SELECT id, nome FROM perfis WHERE nome <> 'Aluno' ORDER BY nome")
        perfil_dd.options = [ft.dropdown.Option(str(p["id"]), p["nome"])
                             for p in perfis]
        lista.controls.clear()
        for u in query("""SELECT u.id, u.nome, u.username, u.ativo,
                                 MAX(up.perfil_id) AS perfil_id,
                                 GROUP_CONCAT(p.nome) AS perfis
                          FROM utilizadores u
                          LEFT JOIN utilizador_perfil up ON up.utilizador_id=u.id
                          LEFT JOIN perfis p ON p.id=up.perfil_id
                          WHERE NOT EXISTS (
                              SELECT 1 FROM utilizador_perfil up_aluno
                              JOIN perfis p_aluno ON p_aluno.id=up_aluno.perfil_id
                              WHERE up_aluno.utilizador_id=u.id AND p_aluno.nome='Aluno'
                          )
                          GROUP BY u.id ORDER BY u.nome"""):
            perfil_utilizador = ft.Dropdown(
                label="Perfil",
                width=160 if (page.width or 1300) < 760 else 220,
                options=[ft.dropdown.Option(str(p["id"]), p["nome"])
                         for p in perfis],
                value=str(u["perfil_id"]) if u["perfil_id"] is not None else None,
                disabled=(u["id"] == S["user"]["id"]),
            )
            guardar_perfil = ft.IconButton(
                ft.Icons.SAVE,
                tooltip="Guardar perfil",
                on_click=lambda e, uid=u["id"], seletor=perfil_utilizador:
                    alterar_perfil(e, uid, seletor),
                disabled=(u["id"] == S["user"]["id"]),
            )
            titulo_utilizador = ft.Text(f"{u['nome']} ({u['username']})")
            detalhe_utilizador = ft.Text(
                "Não pode alterar o próprio perfil."
                if u["id"] == S["user"]["id"]
                else u["perfis"] or "sem perfis"
            )
            acoes = ft.Row([
                perfil_utilizador,
                guardar_perfil,
                ft.IconButton(
                    ft.Icons.DELETE,
                    data=u["id"],
                    on_click=apagar,
                    disabled=(u["id"] == S["user"]["id"]),
                ),
            ], tight=True, spacing=4, wrap=(page.width or 1300) < 760)
            if (page.width or 1300) < 760:
                lista.controls.append(ft.Container(
                    content=ft.Column(
                        [titulo_utilizador, detalhe_utilizador, acoes],
                        spacing=4,
                    ),
                    padding=ft.Padding(8, 12, 8, 12),
                    border=ft.Border.only(bottom=ft.BorderSide(1, "#E2E9E4")),
                ))
            else:
                lista.controls.append(ft.ListTile(
                    title=titulo_utilizador,
                    subtitle=detalhe_utilizador,
                    trailing=acoes,
                ))
        page.update()

    def alterar_perfil(e, utilizador_id, seletor):
        if not pode("responsaveis"):
            erro.value = "Apenas um administrador pode alterar perfis."
            erro.color = VERMELHO
            page.update()
            return

        if utilizador_id == S["user"]["id"]:
            erro.value = "Não pode alterar o próprio perfil."
            erro.color = VERMELHO
            page.update()
            return
        if not seletor.value:
            erro.value = "Selecione um perfil."
            erro.color = VERMELHO
            page.update()
            return

        try:
            execute_transaction([
                ("DELETE FROM utilizador_perfil WHERE utilizador_id=%s",
                 (utilizador_id,)),
                ("INSERT INTO utilizador_perfil (utilizador_id, perfil_id) "
                 "VALUES (%s,%s)", (utilizador_id, int(seletor.value))),
            ])
        except IntegrityError:
            erro.value = "O utilizador ou perfil selecionado já não existe."
            erro.color = VERMELHO
            page.update()
            return

        erro.value = "Perfil do utilizador atualizado."
        erro.color = VERDE
        carregar()

    def apagar(e):
        execute("DELETE FROM utilizadores WHERE id=%s", (e.control.data,))
        carregar()

    def criar(e):
        nome_valor = (nome.value or "").strip()
        user_valor = (user.value or "").strip()
        password = pwd.value or ""
        if not nome_valor or not user_valor or not perfil_dd.value:
            erro.value = "Preencha o nome, o utilizador e selecione um perfil."
            erro.color = VERMELHO
            page.update()
            return
        if len(password) < 6:
            erro.value = "A palavra-passe deve ter pelo menos 6 caracteres."
            erro.color = VERMELHO
            page.update()
            return

        try:
            execute_transaction([
                (
                    "INSERT INTO utilizadores (nome, username, password_hash, ativo) "
                    "VALUES (%s,%s,%s,TRUE)",
                    (nome_valor, user_valor, hash_password(password)),
                ),
                (
                    "INSERT INTO utilizador_perfil (utilizador_id, perfil_id) "
                    "VALUES (LAST_INSERT_ID(),%s)",
                    (int(perfil_dd.value),),
                ),
            ])
        except IntegrityError:
            erro.value = "Este u"
            erro.color = VERMELHO
            page.update()
            return

        nome.value = user.value = pwd.value = ""
        perfil_dd.value = None
        erro.value = "Responsável criado com sucesso."
        erro.color = VERDE
        carregar()

    carregar()
    return ft.Column([
        ft.Text("Responsáveis", size=20, weight=ft.FontWeight.BOLD),
        ft.Row([nome, user, pwd, perfil_dd, ft.Button("Criar", on_click=criar)],
               wrap=True, spacing=8),
        erro,
        ft.Divider(), lista,
    ], scroll=ft.ScrollMode.AUTO, expand=True)

def main(page: ft.Page):
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

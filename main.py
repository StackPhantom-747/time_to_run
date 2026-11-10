import flet as ft
import json
import os
import hashlib
 
ARQUIVO = os.path.join(os.path.dirname(__file__), "alunos.json")
PASSWORD_ADMIN_HASH = hashlib.sha256("1234".encode()).hexdigest()
 
 
def carregar_alunos():
    if not os.path.exists(ARQUIVO):
        guardar_alunos([])
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            dados = json.load(f)
            return dados if isinstance(dados, list) else []
    except (json.JSONDecodeError, OSError):
        return []
 
 
def guardar_alunos(alunos):
    try:
        with open(ARQUIVO, "w", encoding="utf-8") as f:
            json.dump(alunos, f, ensure_ascii=False, indent=4)
        return True
    except OSError:
        return False
 
 
def main(page: ft.Page):
    page.title = "Corta-Mato | Administração"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = "#F1F5F9"
    page.padding = 20
    page.window.width = 1100
    page.window.height = 750
 
    alunos = carregar_alunos()
    pagina_atual = {"valor": "principal"}

    lista_alunos = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    txt_nome = ft.TextField(label="Nome do aluno", width=300)
    txt_turma = ft.TextField(label="Turma", width=200)
    msg = ft.Text("", color=ft.Colors.RED)
 
    def atualizar_lista():
        lista_alunos.controls.clear()
        if not alunos:
            lista_alunos.controls.append(
                ft.Text("Nenhum aluno registado.", italic=True, color=ft.Colors.GREY)
            )
        else:
            for i, a in enumerate(alunos):
                lista_alunos.controls.append(
                    ft.Container(
                        bgcolor=ft.Colors.WHITE,
                        border_radius=8,
                        padding=10,
                        content=ft.Row(
                            [
                                ft.Text(a.get("nome", "?"), weight=ft.FontWeight.BOLD),
                                ft.Text(f"Turma: {a.get('turma', '-')}"),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color=ft.Colors.RED_400,
                                    tooltip="Remover",
                                    on_click=lambda e, idx=i: remover_aluno(idx),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    )
                )
        page.update()
 
    def adicionar_aluno(e):
        nome = txt_nome.value.strip()
        turma = txt_turma.value.strip()
        if not nome:
            msg.value = "O nome é obrigatório."
            page.update()
            return
        alunos.append({"nome": nome, "turma": turma})
        if guardar_alunos(alunos):
            txt_nome.value = ""
            txt_turma.value = ""
            msg.value = ""
            atualizar_lista()
        else:
            msg.value = "Erro ao guardar no ficheiro."
            page.update()
 
    def remover_aluno(idx):
        alunos.pop(idx)
        guardar_alunos(alunos)
        atualizar_lista()
    
    def navegar(e):
        escolha = e.control.value
        pagina_atual["valor"] = escolha
        if escolha == "principal":
            mostrar_principal()
        elif escolha == "definicoes":
            mostrar_definicoes()
 
    def criar_menu_navegacao(pagina):
        dd = ft.Dropdown(
            value=pagina,
            width=220,
            options=[
                ft.dropdown.Option(key="principal", text="Página Principal"),
                ft.dropdown.Option(key="definicoes", text="Definições"),
            ],
        )
        dd.on_change = navegar
        return dd

    def mostrar_definicoes():
        page.controls.clear()
 
        def alternar_tema(e):
            if page.theme_mode == ft.ThemeMode.LIGHT:
                page.theme_mode = ft.ThemeMode.DARK
            else:
                page.theme_mode = ft.ThemeMode.LIGHT
            page.update()
            mostrar_definicoes()
 
        btn_tema = ft.ElevatedButton(
            text="Alternar para modo escuro"
            if page.theme_mode == ft.ThemeMode.LIGHT
            else "Alternar para modo claro",
            on_click=alternar_tema,
        )
 
        page.add(
            ft.Column(
                [
                    criar_menu_navegacao("definicoes"),
                    ft.Divider(),
                    ft.Text("Definições", size=26, weight=ft.FontWeight.BOLD),
                    ft.Text("Aparência", size=18, weight=ft.FontWeight.W_600),
                    btn_tema,
                ],
                spacing=15,
            )
        )
        page.update()

    def mostrar_principal():
        page.controls.clear()
        atualizar_lista()
        page.add(
            ft.Column(
                [
                    criar_menu_navegacao("principal"),
                    ft.Divider(),
                    ft.Text("Gestão de Alunos", size=26, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            txt_nome,
                            txt_turma,
                            ft.ElevatedButton(
                                "Adicionar",
                                icon=ft.Icons.ADD,
                                on_click=adicionar_aluno,
                            ),
                        ]
                    ),
                    msg,
                    ft.Divider(),
                    ft.Text("Alunos registados", size=18, weight=ft.FontWeight.W_600),
                    lista_alunos,
                ],
                expand=True,
                spacing=12,
            )
        )
        page.update()

    txt_password = ft.TextField(
        label="Password de administrador",
        password=True,
        can_reveal_password=True,
        width=300,
    )
    login_msg = ft.Text("", color=ft.Colors.RED)
 
    def tentar_login(e):
        h = hashlib.sha256(txt_password.value.encode()).hexdigest()
        if h == PASSWORD_ADMIN_HASH:
            mostrar_principal()
        else:
            login_msg.value = "Password incorreta."
            page.update()
 
    def ecra_login():
        page.controls.clear()
        page.add(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER, 
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.LOCK_OUTLINE, size=48, color=ft.Colors.BLUE_400),
                        ft.Text("Administração", size=24, weight=ft.FontWeight.BOLD),
                        txt_password,
                        ft.ElevatedButton("Entrar", on_click=tentar_login),
                        login_msg,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=15,
                    tight=True,
                ),
            )
        )
        page.update()
 
    ecra_login()
 
 
if __name__ == "__main__":
    ft.app(target=main)
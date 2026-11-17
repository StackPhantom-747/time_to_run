from db import execute, query
from auth import hash_password, verificar

PERFIS = ["Administrador", "Secretariado Inscrições", "Secretariado Partida",
          "Secretariado Meta", "Consulta"]

ESCALOES = [("Infantis A", 10, 11), ("Infantis B", 12, 13), ("Iniciados", 14, 15),
            ("Juvenis", 16, 17), ("Juniores", 18, 19)]

execute("""CREATE TABLE IF NOT EXISTS regras_apuramento (
    id INT AUTO_INCREMENT PRIMARY KEY,
    escalao_id INT NOT NULL,
    indicador_da BOOLEAN NOT NULL DEFAULT FALSE,
    num_apurados INT NOT NULL DEFAULT 0,
    fase_seguinte VARCHAR(150),
    UNIQUE (escalao_id, indicador_da),
    FOREIGN KEY (escalao_id) REFERENCES escaloes(id)
)""")

for p in PERFIS:
    if not query("SELECT id FROM perfis WHERE nome=%s", (p,), one=True):
        execute("INSERT INTO perfis (nome) VALUES (%s)", (p,))

admin = query("SELECT id, password_hash FROM utilizadores WHERE username='admin'", one=True)
if not admin:
    uid = execute(
        "INSERT INTO utilizadores (nome, username, password_hash, email, ativo) "
        "VALUES (%s,%s,%s,%s,%s)",
        ("Administrador", "admin", hash_password("admin123"), None, True)
    )
    pid = query("SELECT id FROM perfis WHERE nome='Administrador'", one=True)["id"]
    execute("INSERT INTO utilizador_perfil (utilizador_id, perfil_id) VALUES (%s,%s)", (uid, pid))
    print("admin criado: admin / admin123")
else:
    uid = admin["id"]
    if not verificar("admin123", admin["password_hash"]):
        execute("UPDATE utilizadores SET password_hash=%s, ativo=TRUE WHERE id=%s",
                (hash_password("admin123"), uid))
        print("hash do admin reposto para admin123")
    else:
        print("admin já existia e o hash está válido")

if not query("SELECT id FROM escaloes LIMIT 1", one=True):
    for g in ("M", "F"):
        for nome, a, b in ESCALOES:
            execute("INSERT INTO escaloes (nome, genero, idade_minima, idade_maxima) "
                    "VALUES (%s,%s,%s,%s)", (nome, g, a, b))
    print("escalões criados")

print("Concluído.")
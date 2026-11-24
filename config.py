import os

APP_TITLE = "RC-PSI · Corta-Mato Escolar"

DB_CONFIG = {
    "host": os.getenv("RC_DB_HOST", "localhost"),
    "port": int(os.getenv("RC_DB_PORT", "3306")),
    "user": os.getenv("RC_DB_USER", "root"),
    "password": os.getenv("RC_DB_PASSWORD", ""),
    "database": os.getenv("RC_DB_NAME", "rc_psi"),
    "charset": "utf8mb4",
}

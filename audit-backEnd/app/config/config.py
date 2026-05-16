from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

CLOUD_ROOT = PROJECT_ROOT / "Cloud"
SQLITE_ROOT = PROJECT_ROOT / "MySQLite"
USER_DB_PATH = SQLITE_ROOT / "user.db"
AUDIT_DB_PATH = SQLITE_ROOT / "audit.db"

USER_ID_COUNT_MIN = 1
USER_ID_COUNT_MAX = 99

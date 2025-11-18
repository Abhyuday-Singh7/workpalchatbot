from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables explicitly from the project-root .env if present
load_dotenv(BASE_DIR / ".env")

# Base data directory where department folders will live
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# SQLite database path
DATABASE_URL = f"sqlite:///{(BASE_DIR / 'workpal.db').as_posix()}"


def get_department_data_dir(department: str) -> Path:
    """
    Return the base directory for a given department under DATA_DIR.
    Example: /data/hr
    """
    dept_dir = DATA_DIR / department.lower()
    dept_dir.mkdir(parents=True, exist_ok=True)
    (dept_dir / "instructions").mkdir(parents=True, exist_ok=True)
    return dept_dir

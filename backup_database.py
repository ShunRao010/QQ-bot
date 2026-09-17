import sqlite3
from datetime import datetime
from pathlib import Path

SOURCE_DB = Path("data/qq_team_bot.db")
BACKUP_DIR = Path("backups")


def main() -> None:
    if not SOURCE_DB.exists():
        raise FileNotFoundError(
            f"Database not found: {SOURCE_DB}"
        )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    month = datetime.now().strftime("%Y-%m")

    backup_path = (
        BACKUP_DIR
        / f"qq_team_bot_{month}.db"
    )

    source = sqlite3.connect(SOURCE_DB)
    backup = sqlite3.connect(backup_path)

    try:
        source.backup(backup)
    finally:
        backup.close()
        source.close()

    print(
        f"Database backup completed: "
        f"{backup_path}"
    )


if __name__ == "__main__":
    main()

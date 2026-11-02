import os
import sqlite3
from pathlib import Path

#DB_PATH = Path("data/qq_team_bot.db")
DB_PATH = Path(
    os.environ.get("QQ_TEAM_BOT_DB", "data/qq_team_bot.db")
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS group_sequences (
    group_id INTEGER PRIMARY KEY,
    next_party_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS last_party_settings (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,

    max_size INTEGER NOT NULL,
    start_time TEXT,
    description TEXT NOT NULL,

    PRIMARY KEY (group_id, user_id),

    CHECK (max_size BETWEEN 2 AND 50),
    CHECK (length(description) BETWEEN 1 AND 100)
);

CREATE TABLE IF NOT EXISTS parties (
    group_id INTEGER NOT NULL,
    party_id INTEGER NOT NULL,

    creator_id INTEGER NOT NULL,
    start_at INTEGER NOT NULL,
    max_size INTEGER NOT NULL,
    description TEXT NOT NULL,

    status TEXT NOT NULL
        CHECK (status IN ('OPEN', 'FULL', 'DISBANDED', 'EXPIRED')),

    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    reminder_sent INTEGER NOT NULL DEFAULT 0,
    disbanded_at INTEGER,

    PRIMARY KEY (group_id, party_id),

    CHECK (max_size BETWEEN 2 AND 50),
    CHECK (length(description) BETWEEN 1 AND 100)
);

CREATE TABLE IF NOT EXISTS party_members (
    group_id INTEGER NOT NULL,
    party_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at INTEGER NOT NULL,

    PRIMARY KEY (group_id, party_id, user_id),

    FOREIGN KEY (group_id, party_id)
        REFERENCES parties (group_id, party_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_parties_group_status
    ON parties (group_id, status);

CREATE INDEX IF NOT EXISTS idx_parties_expires_at
    ON parties (expires_at);

CREATE INDEX IF NOT EXISTS idx_party_members_user
    ON party_members (group_id, user_id);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row

    return conn


def initialize_database() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(parties)"
            ).fetchall()
        }

        if "start_at" not in columns:
            conn.execute(
                "ALTER TABLE parties ADD COLUMN start_at INTEGER"
            )
            conn.execute(
                """
                UPDATE parties
                SET start_at = created_at
                WHERE start_at IS NULL
                """
            )

        if "reminder_sent" not in columns:
            conn.execute(
                """
                ALTER TABLE parties
                ADD COLUMN reminder_sent INTEGER NOT NULL DEFAULT 0
                """
            )

def create_party(
    group_id: int,
    creator_id: int,
    max_size: int,
    description: str,
    created_at: int,
    start_at: int | None = None,
) -> int:
    description = description.strip()

    if not 2 <= max_size <= 50:
        raise ValueError("max_size must be between 2 and 50")

    if not 1 <= len(description) <= 100:
        raise ValueError("description must be between 1 and 100 characters")

    explicit_start_time = start_at is not None

    if start_at is None:
        start_at = created_at

    expires_at = start_at + 6 * 60 * 60

    # 只有显式设置、并且至少提前 15 分钟的队伍需要等待提醒。
    # 其他情况直接标记为“不需要提醒”。
    reminder_sent = 0 if (
        explicit_start_time
        and start_at - created_at >= 15 * 60
    ) else 1

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT next_party_id
            FROM group_sequences
            WHERE group_id = ?
            """,
            (group_id,),
        ).fetchone()

        if row is None:
            party_id = 1

            conn.execute(
                """
                INSERT INTO group_sequences (
                    group_id,
                    next_party_id
                )
                VALUES (?, ?)
                """,
                (group_id, 2),
            )
        else:
            party_id = row["next_party_id"]

            conn.execute(
                """
                UPDATE group_sequences
                SET next_party_id = ?
                WHERE group_id = ?
                """,
                (party_id + 1, group_id),
            )

        conn.execute(
            """
            INSERT INTO parties (
                group_id,
                party_id,
                creator_id,
                max_size,
                description,
                status,
                created_at,
                start_at,
                expires_at,
                reminder_sent
            )
            VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?, ?, ?)
            """,
            (
                group_id,
                party_id,
                creator_id,
                max_size,
                description,
                created_at,
                start_at,
                expires_at,
                reminder_sent,
            ),
        )

        conn.execute(
            """
            INSERT INTO party_members (
                group_id,
                party_id,
                user_id,
                joined_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                group_id,
                party_id,
                creator_id,
                created_at,
            ),
        )

        return party_id


def expire_parties(
    group_id: int,
    now: int,
) -> int:
    """
    Lazily mark expired OPEN/FULL parties as EXPIRED.

    Returns:
        Number of parties changed to EXPIRED.
    """

    with connect() as conn:
        cursor = conn.execute(
            """
            UPDATE parties
            SET status = 'EXPIRED'
            WHERE group_id = ?
              AND status IN ('OPEN', 'FULL')
              AND expires_at <= ?
            """,
            (group_id, now),
        )

        return cursor.rowcount


def join_party(
    group_id: int,
    party_id: int,
    user_id: int,
    now: int,
) -> None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        party = conn.execute(
            """
            SELECT status, max_size, expires_at
            FROM parties
            WHERE group_id = ?
              AND party_id = ?
            """,
            (group_id, party_id),
        ).fetchone()

        if party is None:
            raise ValueError("PARTY_NOT_FOUND")

        if (
            party["status"] in ("OPEN", "FULL")
            and party["expires_at"] <= now
        ):
            conn.execute(
                """
                UPDATE parties
                SET status = 'EXPIRED'
                WHERE group_id = ?
                  AND party_id = ?
                """,
                (group_id, party_id),
            )
            raise ValueError("PARTY_EXPIRED")

        if party["status"] == "EXPIRED":
            raise ValueError("PARTY_EXPIRED")

        if party["status"] == "DISBANDED":
            raise ValueError("PARTY_DISBANDED")

        existing = conn.execute(
            """
            SELECT 1
            FROM party_members
            WHERE group_id = ?
              AND party_id = ?
              AND user_id = ?
            """,
            (group_id, party_id, user_id),
        ).fetchone()

        if existing is not None:
            raise ValueError("ALREADY_MEMBER")

        member_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM party_members
            WHERE group_id = ?
              AND party_id = ?
            """,
            (group_id, party_id),
        ).fetchone()["count"]

        if (
            party["status"] == "FULL"
            or member_count >= party["max_size"]
        ):
            raise ValueError("PARTY_FULL")

        conn.execute(
            """
            INSERT INTO party_members (
                group_id,
                party_id,
                user_id,
                joined_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (group_id, party_id, user_id, now),
        )

        new_count = member_count + 1

        if new_count >= party["max_size"]:
            conn.execute(
                """
                UPDATE parties
                SET status = 'FULL'
                WHERE group_id = ?
                  AND party_id = ?
                """,
                (group_id, party_id),
            )


def leave_party(
    group_id: int,
    party_id: int,
    user_id: int,
    now: int,
) -> None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        party = conn.execute(
            """
            SELECT creator_id, status, expires_at
            FROM parties
            WHERE group_id = ?
              AND party_id = ?
            """,
            (group_id, party_id),
        ).fetchone()

        if party is None:
            raise ValueError("PARTY_NOT_FOUND")

        if (
            party["status"] in ("OPEN", "FULL")
            and party["expires_at"] <= now
        ):
            conn.execute(
                """
                UPDATE parties
                SET status = 'EXPIRED'
                WHERE group_id = ?
                  AND party_id = ?
                """,
                (group_id, party_id),
            )
            raise ValueError("PARTY_EXPIRED")

        if party["status"] == "EXPIRED":
            raise ValueError("PARTY_EXPIRED")

        if party["status"] == "DISBANDED":
            raise ValueError("PARTY_DISBANDED")

        if party["creator_id"] == user_id:
            raise ValueError("CREATOR_CANNOT_LEAVE")

        member = conn.execute(
            """
            SELECT 1
            FROM party_members
            WHERE group_id = ?
              AND party_id = ?
              AND user_id = ?
            """,
            (group_id, party_id, user_id),
        ).fetchone()

        if member is None:
            raise ValueError("NOT_MEMBER")

        conn.execute(
            """
            DELETE FROM party_members
            WHERE group_id = ?
              AND party_id = ?
              AND user_id = ?
            """,
            (group_id, party_id, user_id),
        )

        if party["status"] == "FULL":
            conn.execute(
                """
                UPDATE parties
                SET status = 'OPEN'
                WHERE group_id = ?
                  AND party_id = ?
                """,
                (group_id, party_id),
            )


def disband_party(
    group_id: int,
    party_id: int,
    user_id: int,
    now: int,
    is_admin: bool = False,
) -> None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        party = conn.execute(
            """
            SELECT creator_id, status, expires_at
            FROM parties
            WHERE group_id = ?
              AND party_id = ?
            """,
            (group_id, party_id),
        ).fetchone()

        if party is None:
            raise ValueError("PARTY_NOT_FOUND")

        if (
            party["status"] in ("OPEN", "FULL")
            and party["expires_at"] <= now
        ):
            conn.execute(
                """
                UPDATE parties
                SET status = 'EXPIRED'
                WHERE group_id = ?
                  AND party_id = ?
                """,
                (group_id, party_id),
            )
            raise ValueError("PARTY_EXPIRED")

        if party["status"] == "EXPIRED":
            raise ValueError("PARTY_EXPIRED")

        if party["status"] == "DISBANDED":
            raise ValueError("PARTY_DISBANDED")

        if party["creator_id"] != user_id and not is_admin:
            raise ValueError("NO_PERMISSION")

        conn.execute(
            """
            UPDATE parties
            SET status = 'DISBANDED',
                disbanded_at = ?
            WHERE group_id = ?
              AND party_id = ?
            """,
            (now, group_id, party_id),
        )


def get_party(
    group_id: int,
    party_id: int,
    now: int,
) -> dict | None:
    expire_parties(group_id, now)

    with connect() as conn:
        party = conn.execute(
            """
            SELECT
                group_id,
                party_id,
                creator_id,
                max_size,
                description,
                status,
                created_at,
                start_at,
                expires_at,
                reminder_sent,
                disbanded_at
            FROM parties
            WHERE group_id = ?
              AND party_id = ?
            """,
            (group_id, party_id),
        ).fetchone()

        if party is None:
            return None

        members = conn.execute(
            """
            SELECT
                user_id,
                joined_at
            FROM party_members
            WHERE group_id = ?
              AND party_id = ?
            ORDER BY joined_at ASC, user_id ASC
            """,
            (group_id, party_id),
        ).fetchall()

    result = dict(party)
    result["members"] = [dict(member) for member in members]
    result["member_count"] = len(members)

    return result


def list_active_parties(
    group_id: int,
    now: int,
) -> list[dict]:
    expire_parties(group_id, now)

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                p.group_id,
                p.party_id,
                p.creator_id,
                p.max_size,
                p.description,
                p.status,
                p.created_at,
                p.start_at,
                p.expires_at,
                COUNT(pm.user_id) AS member_count
            FROM parties AS p
            LEFT JOIN party_members AS pm
                ON pm.group_id = p.group_id
               AND pm.party_id = p.party_id
            WHERE p.group_id = ?
              AND p.status IN ('OPEN', 'FULL')
            GROUP BY
                p.group_id,
                p.party_id,
                p.creator_id,
                p.max_size,
                p.description,
                p.status,
                p.created_at,
                p.start_at,
                p.expires_at
            ORDER BY p.party_id ASC
            """,
            (group_id,),
        ).fetchall()

    return [dict(row) for row in rows]



def handle_group_member_leave(
    group_id: int,
    user_id: int,
    now: int,
) -> None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")

        # 先处理已经到期的活动队伍
        conn.execute(
            """
            UPDATE parties
            SET status = 'EXPIRED'
            WHERE group_id = ?
              AND status IN ('OPEN', 'FULL')
              AND expires_at <= ?
            """,
            (group_id, now),
        )

        # 如果退群者是创建者，其仍然有效的队伍全部解散
        conn.execute(
            """
            UPDATE parties
            SET status = 'DISBANDED',
                disbanded_at = ?
            WHERE group_id = ?
              AND creator_id = ?
              AND status IN ('OPEN', 'FULL')
            """,
            (now, group_id, user_id),
        )

        # 找出该成员参加、但不是其创建的活动队伍
        memberships = conn.execute(
            """
            SELECT
                p.party_id,
                p.status
            FROM party_members AS pm
            JOIN parties AS p
              ON p.group_id = pm.group_id
             AND p.party_id = pm.party_id
            WHERE pm.group_id = ?
              AND pm.user_id = ?
              AND p.creator_id != ?
              AND p.status IN ('OPEN', 'FULL')
            """,
            (group_id, user_id, user_id),
        ).fetchall()

        for membership in memberships:
            conn.execute(
                """
                DELETE FROM party_members
                WHERE group_id = ?
                  AND party_id = ?
                  AND user_id = ?
                """,
                (
                    group_id,
                    membership["party_id"],
                    user_id,
                ),
            )

            # FULL 队伍失去一个成员后重新开放
            if membership["status"] == "FULL":
                conn.execute(
                    """
                    UPDATE parties
                    SET status = 'OPEN'
                    WHERE group_id = ?
                      AND party_id = ?
                    """,
                    (
                        group_id,
                        membership["party_id"],
                    ),
                )


def list_user_active_parties(
    group_id: int,
    user_id: int,
    now: int,
) -> list[dict]:
    expire_parties(group_id, now)

    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                p.party_id,
                p.creator_id,
                p.max_size,
                p.description,
                p.status,
                p.created_at,
                p.start_at,
                p.expires_at
            FROM party_members AS pm
            JOIN parties AS p
              ON p.group_id = pm.group_id
             AND p.party_id = pm.party_id
            WHERE pm.group_id = ?
              AND pm.user_id = ?
              AND p.status IN ('OPEN', 'FULL')
            ORDER BY p.party_id ASC
            """,
            (group_id, user_id),
        ).fetchall()

    return [dict(row) for row in rows]

def list_due_reminders(
    now: int,
) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                group_id,
                party_id,
                start_at
            FROM parties
            WHERE status IN ('OPEN', 'FULL')
              AND reminder_sent = 0
              AND start_at - 15 * 60 <= ?
              AND start_at > ?
            ORDER BY start_at ASC
            """,
            (now, now),
        ).fetchall()

    return [dict(row) for row in rows]


def mark_reminder_sent(
    group_id: int,
    party_id: int,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE parties
            SET reminder_sent = 1
            WHERE group_id = ?
              AND party_id = ?
            """,
            (group_id, party_id),
        )

def save_last_party_settings(
    group_id: int,
    user_id: int,
    max_size: int,
    start_time: str | None,
    description: str,
) -> None:
    description = description.strip()

    if not 2 <= max_size <= 50:
        raise ValueError("max_size must be between 2 and 50")

    if not 1 <= len(description) <= 100:
        raise ValueError("description must be between 1 and 100 characters")

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO last_party_settings (
                group_id,
                user_id,
                max_size,
                start_time,
                description
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (group_id, user_id)
            DO UPDATE SET
                max_size = excluded.max_size,
                start_time = excluded.start_time,
                description = excluded.description
            """,
            (
                group_id,
                user_id,
                max_size,
                start_time,
                description,
            ),
        )


def get_last_party_settings(
    group_id: int,
    user_id: int,
) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT
                max_size,
                start_time,
                description
            FROM last_party_settings
            WHERE group_id = ?
              AND user_id = ?
            """,
            (
                group_id,
                user_id,
            ),
        ).fetchone()

    if row is None:
        return None

    return dict(row)

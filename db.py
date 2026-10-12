import sqlite3
import json

DB_PATH = "fc_agent.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            match_id        TEXT,
            ouid            TEXT,
            nickname        TEXT,
            match_date      TEXT,
            result          TEXT,
            my_goal         INTEGER,
            opp_goal        INTEGER,
            opp_nickname    TEXT,
            possession      INTEGER,
            shoot_total     INTEGER,
            shoot_effective INTEGER,
            shoot_out_box   INTEGER,
            goal_out_box    INTEGER,
            pass_try        INTEGER,
            pass_success    INTEGER,
            is_forfeit      INTEGER,
            raw_json        TEXT,
            PRIMARY KEY (match_id, ouid)
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tactic_changes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ouid        TEXT NOT NULL,
            change_date TEXT NOT NULL,
            memo        TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """)


# ---------- 경기 기록 ----------

def match_exists(match_id, ouid):
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM matches WHERE match_id=? AND ouid=?",
                           (match_id, ouid)).fetchone()
        return row is not None


def save_match(detail, ouid):
    players = detail.get("matchInfo", [])
    me = next((p for p in players if p.get("ouid") == ouid), None)
    opp = next((p for p in players if p.get("ouid") != ouid), None)
    if not me or not opp:
        return False

    md = me.get("matchDetail", {}) or {}
    shoot = me.get("shoot", {}) or {}
    pss = me.get("pass", {}) or {}
    opp_shoot = opp.get("shoot", {}) or {}

    # 몰수 경기: 종료 유형이 정상(0)이 아니거나 상대 기록이 비어 있는 경우
    is_forfeit = 1 if md.get("matchEndType", 0) != 0 or not opp_shoot else 0

    with get_conn() as conn:
        conn.execute("""
        INSERT OR IGNORE INTO matches VALUES
        (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            detail.get("matchId"), ouid, me.get("nickname"), detail.get("matchDate"),
            md.get("matchResult"), shoot.get("goalTotal"), opp_shoot.get("goalTotal"),
            opp.get("nickname"), md.get("possession"),
            shoot.get("shootTotal"), shoot.get("effectiveShootTotal"),
            shoot.get("shootOutPenalty"), shoot.get("goalOutPenalty"),
            pss.get("passTry"), pss.get("passSuccess"),
            is_forfeit, json.dumps(detail, ensure_ascii=False),
        ))
    return True


# ---------- 전술 변경 기록 ----------

def add_tactic_change(ouid, change_date, memo):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tactic_changes (ouid, change_date, memo) VALUES (?,?,?)",
            (ouid, change_date, memo))
        return cur.lastrowid


def list_tactic_changes(ouid):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, change_date, memo FROM tactic_changes
            WHERE ouid=? ORDER BY change_date DESC
        """, (ouid,)).fetchall()
    return [dict(r) for r in rows]


def delete_tactic_change(change_id, ouid):
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM tactic_changes WHERE id=? AND ouid=?",
                           (change_id, ouid))
        return cur.rowcount > 0
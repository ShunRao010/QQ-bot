import os
from pathlib import Path

TEST_DB = Path("data/test_qq_team_bot.db")

os.environ["QQ_TEAM_BOT_DB"] = str(TEST_DB)

from src.database import (
    connect,
    create_party,
    disband_party,
    expire_parties,
    get_party,
    initialize_database,
    join_party,
    leave_party,
    list_active_parties,
    handle_group_member_leave,
    list_user_active_parties,
    get_last_party_settings,
    save_last_party_settings,
)

if TEST_DB.exists():
    TEST_DB.unlink()

initialize_database()

created_at = 1_700_000_000

party_id = create_party(
    group_id=123456,
    creator_id=10001,
    max_size=5,
    description="测试队伍",
    created_at=created_at,
)

assert party_id == 1

with connect() as conn:
    party = conn.execute(
        """
        SELECT *
        FROM parties
        WHERE group_id = ? AND party_id = ?
        """,
        (123456, 1),
    ).fetchone()

    members = conn.execute(
        """
        SELECT *
        FROM party_members
        WHERE group_id = ? AND party_id = ?
        """,
        (123456, 1),
    ).fetchall()

assert party is not None
assert party["creator_id"] == 10001
assert party["max_size"] == 5
assert party["description"] == "测试队伍"
assert party["status"] == "OPEN"
assert party["created_at"] == created_at
assert party["start_at"] == created_at
assert party["expires_at"] == party["start_at"] + 6 * 60 * 60

assert len(members) == 1
assert members[0]["user_id"] == 10001
party_id_2 = create_party(
    group_id=123456,
    creator_id=10002,
    max_size=3,
    description="第二个测试队伍",
    created_at=created_at + 10,
)

party_id_3 = create_party(
    group_id=123456,
    creator_id=10003,
    max_size=10,
    description="第三个测试队伍",
    created_at=created_at + 20,
)

assert party_id_2 == 2
assert party_id_3 == 3

# #001 在 start_at + 6h 的前一秒仍然有效
changed = expire_parties(
    group_id=123456,
    now=created_at + 6 * 60 * 60 - 1,
)

assert changed == 0

# 到达恰好 6h 时，#001 应过期
changed = expire_parties(
    group_id=123456,
    now=created_at + 6 * 60 * 60,
)

assert changed == 1

with connect() as conn:
    party = conn.execute(
        """
        SELECT status
        FROM parties
        WHERE group_id = ? AND party_id = ?
        """,
        (123456, 1),
    ).fetchone()

assert party is not None
assert party["status"] == "EXPIRED"

# 创建一个容量为 2 的新队伍用于测试 join
join_test_id = create_party(
    group_id=123456,
    creator_id=20001,
    max_size=2,
    description="Join测试队伍",
    created_at=created_at + 100,
)

assert join_test_id == 4

# 第二名成员加入，应占满队伍
join_party(
    group_id=123456,
    party_id=join_test_id,
    user_id=20002,
    now=created_at + 101,
)

with connect() as conn:
    party = conn.execute(
        """
        SELECT status
        FROM parties
        WHERE group_id = ?
          AND party_id = ?
        """,
        (123456, join_test_id),
    ).fetchone()

    member_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM party_members
        WHERE group_id = ?
          AND party_id = ?
        """,
        (123456, join_test_id),
    ).fetchone()["count"]

assert party is not None
assert party["status"] == "FULL"
assert member_count == 2

# 同一成员不能重复加入
try:
    join_party(
        group_id=123456,
        party_id=join_test_id,
        user_id=20002,
        now=created_at + 102,
    )
except ValueError as exc:
    assert str(exc) == "ALREADY_MEMBER"
else:
    raise AssertionError("duplicate join should fail")

# 第三名成员不能加入已经满员的队伍
try:
    join_party(
        group_id=123456,
        party_id=join_test_id,
        user_id=20003,
        now=created_at + 103,
    )
except ValueError as exc:
    assert str(exc) == "PARTY_FULL"
else:
    raise AssertionError("joining a full party should fail")

# #004 当前为 FULL，普通成员退出后应恢复 OPEN
leave_party(
    group_id=123456,
    party_id=join_test_id,
    user_id=20002,
    now=created_at + 104,
)

with connect() as conn:
    party = conn.execute(
        """
        SELECT status
        FROM parties
        WHERE group_id = ?
          AND party_id = ?
        """,
        (123456, join_test_id),
    ).fetchone()

    member_count = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM party_members
        WHERE group_id = ?
          AND party_id = ?
        """,
        (123456, join_test_id),
    ).fetchone()["count"]

assert party is not None
assert party["status"] == "OPEN"
assert member_count == 1

# 已退出的成员不能再次退出
try:
    leave_party(
        group_id=123456,
        party_id=join_test_id,
        user_id=20002,
        now=created_at + 105,
    )
except ValueError as exc:
    assert str(exc) == "NOT_MEMBER"
else:
    raise AssertionError("non-member leave should fail")

# 创建者不能通过普通退出离开自己的队伍
try:
    leave_party(
        group_id=123456,
        party_id=join_test_id,
        user_id=20001,
        now=created_at + 106,
    )
except ValueError as exc:
    assert str(exc) == "CREATOR_CANNOT_LEAVE"
else:
    raise AssertionError("creator leave should fail")

# 创建 #005，用于测试解散权限
disband_test_id = create_party(
    group_id=123456,
    creator_id=30001,
    max_size=5,
    description="解散测试队伍",
    created_at=created_at + 200,
)

assert disband_test_id == 5

# 普通非创建者不能解散
try:
    disband_party(
        group_id=123456,
        party_id=disband_test_id,
        user_id=30002,
        now=created_at + 201,
        is_admin=False,
    )
except ValueError as exc:
    assert str(exc) == "NO_PERMISSION"
else:
    raise AssertionError("non-creator disband should fail")

# 创建者可以解散
disband_party(
    group_id=123456,
    party_id=disband_test_id,
    user_id=30001,
    now=created_at + 202,
)

with connect() as conn:
    party = conn.execute(
        """
        SELECT status, disbanded_at
        FROM parties
        WHERE group_id = ?
          AND party_id = ?
        """,
        (123456, disband_test_id),
    ).fetchone()

assert party is not None
assert party["status"] == "DISBANDED"
assert party["disbanded_at"] == created_at + 202


# 创建 #006，用于测试管理员强制解散
admin_disband_test_id = create_party(
    group_id=123456,
    creator_id=40001,
    max_size=5,
    description="管理员解散测试队伍",
    created_at=created_at + 300,
)

assert admin_disband_test_id == 6

# 非创建者，但具有管理员权限，可以强制解散
disband_party(
    group_id=123456,
    party_id=admin_disband_test_id,
    user_id=40002,
    now=created_at + 301,
    is_admin=True,
)

with connect() as conn:
    party = conn.execute(
        """
        SELECT status, disbanded_at
        FROM parties
        WHERE group_id = ?
          AND party_id = ?
        """,
        (123456, admin_disband_test_id),
    ).fetchone()

assert party is not None
assert party["status"] == "DISBANDED"
assert party["disbanded_at"] == created_at + 301

# 测试 get_party 查询
party = get_party(
    group_id=123456,
    party_id=join_test_id,
    now=created_at + 400,
)

assert party is not None
assert party["party_id"] == join_test_id
assert party["creator_id"] == 20001
assert party["max_size"] == 2
assert party["description"] == "Join测试队伍"
assert party["status"] == "OPEN"
assert party["member_count"] == 1

assert len(party["members"]) == 1
assert party["members"][0]["user_id"] == 20001

# 不存在的队伍应返回 None
missing_party = get_party(
    group_id=123456,
    party_id=999,
    now=created_at + 400,
)

assert missing_party is None

# 测试活动队伍列表
active_parties = list_active_parties(
    group_id=123456,
    now=created_at + 400,
)

active_ids = [
    party["party_id"]
    for party in active_parties
]

# #001 已过期
assert 1 not in active_ids

# #004 仍为 OPEN
assert join_test_id in active_ids

# #005、#006 已解散
assert disband_test_id not in active_ids
assert admin_disband_test_id not in active_ids

# 检查 #004 的概要信息
join_test_summary = next(
    party
    for party in active_parties
    if party["party_id"] == join_test_id
)

assert join_test_summary["status"] == "OPEN"
assert join_test_summary["member_count"] == 1
assert join_test_summary["max_size"] == 2


# 创建 #007，用于测试 FULL 队伍仍出现在活动列表
full_list_test_id = create_party(
    group_id=123456,
    creator_id=50001,
    max_size=2,
    description="FULL列表测试队伍",
    created_at=created_at + 500,
)

assert full_list_test_id == 7

join_party(
    group_id=123456,
    party_id=full_list_test_id,
    user_id=50002,
    now=created_at + 501,
)

active_parties = list_active_parties(
    group_id=123456,
    now=created_at + 502,
)

full_summary = next(
    party
    for party in active_parties
    if party["party_id"] == full_list_test_id
)

assert full_summary["status"] == "FULL"
assert full_summary["member_count"] == 2
assert full_summary["max_size"] == 2

# 普通成员退出 QQ 群：
# #007 当前为 FULL，50002 退群后应被移除，并恢复 OPEN
handle_group_member_leave(
    group_id=123456,
    user_id=50002,
    now=created_at + 600,
)

party = get_party(
    group_id=123456,
    party_id=full_list_test_id,
    now=created_at + 600,
)

assert party is not None
assert party["status"] == "OPEN"
assert party["member_count"] == 1
assert party["members"][0]["user_id"] == 50001

# 创建者退出 QQ 群：
# 创建 #008，并让另一名成员加入
creator_leave_test_id = create_party(
    group_id=123456,
    creator_id=60001,
    max_size=3,
    description="创建者退群测试队伍",
    created_at=created_at + 700,
)

assert creator_leave_test_id == 8

join_party(
    group_id=123456,
    party_id=creator_leave_test_id,
    user_id=60002,
    now=created_at + 701,
)

# 创建者退出 QQ 群
handle_group_member_leave(
    group_id=123456,
    user_id=60001,
    now=created_at + 702,
)

party = get_party(
    group_id=123456,
    party_id=creator_leave_test_id,
    now=created_at + 702,
)

assert party is not None
assert party["status"] == "DISBANDED"
assert party["disbanded_at"] == created_at + 702

# soft disband：历史成员关系仍然保留
assert party["member_count"] == 2

member_ids = {
    member["user_id"]
    for member in party["members"]
}

assert member_ids == {60001, 60002}

# 测试同一成员可以同时参加多个活动队伍
multi_user_id = 70001

multi_party_1 = create_party(
    group_id=123456,
    creator_id=70002,
    max_size=5,
    description="多队伍测试一",
    created_at=created_at + 800,
)

multi_party_2 = create_party(
    group_id=123456,
    creator_id=70003,
    max_size=5,
    description="多队伍测试二",
    created_at=created_at + 801,
)

assert multi_party_1 == 9
assert multi_party_2 == 10

join_party(
    group_id=123456,
    party_id=multi_party_1,
    user_id=multi_user_id,
    now=created_at + 802,
)

join_party(
    group_id=123456,
    party_id=multi_party_2,
    user_id=multi_user_id,
    now=created_at + 803,
)

user_parties = list_user_active_parties(
    group_id=123456,
    user_id=multi_user_id,
    now=created_at + 804,
)

user_party_ids = [
    party["party_id"]
    for party in user_parties
]

assert user_party_ids == [
    multi_party_1,
    multi_party_2,
]

# 测试上一次起队输入模板
last_settings_group = 888888
last_settings_user = 777777

# 第一次没有历史
assert get_last_party_settings(
    group_id=last_settings_group,
    user_id=last_settings_user,
) is None

# 保存第一次模板
save_last_party_settings(
    group_id=last_settings_group,
    user_id=last_settings_user,
    max_size=5,
    start_time="20:30",
    description="晚上刷副本",
)

settings = get_last_party_settings(
    group_id=last_settings_group,
    user_id=last_settings_user,
)

assert settings == {
    "max_size": 5,
    "start_time": "20:30",
    "description": "晚上刷副本",
}

# 同一群、同一用户再次起队，应覆盖旧模板
save_last_party_settings(
    group_id=last_settings_group,
    user_id=last_settings_user,
    max_size=3,
    start_time="21:45",
    description="新版队伍",
)

settings = get_last_party_settings(
    group_id=last_settings_group,
    user_id=last_settings_user,
)

assert settings == {
    "max_size": 3,
    "start_time": "21:45",
    "description": "新版队伍",
}

# 不同群不能共享模板
assert get_last_party_settings(
    group_id=999999,
    user_id=last_settings_user,
) is None

# 不同用户不能共享模板
assert get_last_party_settings(
    group_id=last_settings_group,
    user_id=666666,
) is None

print("create_party sequence test passed")
print(
    f"#{party_id:03d} "
    f"#{party_id_2:03d} "
    f"#{party_id_3:03d}"
)

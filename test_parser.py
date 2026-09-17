from src.message_parser import (
    parse_leave_command,
    extract_command,
    parse_create_command,
    parse_party_id,
    parse_join_command,
    parse_view_command,
    parse_disband_command,
    parse_list_command,
    parse_help_command,
    parse_command,
)

normal_event = {
    "self_id": 2330607644,
    "post_type": "message",
    "message_type": "group",
    "message": [
        {
            "type": "text",
            "data": {"text": "测试一下"},
        }
    ],
}

at_bot_event = {
    "self_id": 2330607644,
    "post_type": "message",
    "message_type": "group",
    "message": [
        {
            "type": "at",
            "data": {"qq": "2330607644"},
        },
        {
            "type": "text",
            "data": {"text": " 测试"},
        },
    ],
}


assert extract_command(normal_event) is None
assert extract_command(at_bot_event) == "测试"

assert parse_party_id("#001") == 1
assert parse_party_id("#023") == 23
assert parse_party_id("#999") == 999
assert parse_party_id("#1000") == 1000

assert parse_party_id("001") is None
assert parse_party_id("1") is None
assert parse_party_id("#1") is None
assert parse_party_id("#01") is None
assert parse_party_id("#000") is None
assert parse_party_id("#abc") is None
assert parse_party_id("#-1") is None
assert parse_party_id("") is None

assert parse_create_command(
    "起队 5 深渊副本"
) == {
    "action": "create",
    "max_size": 5,
    "description": "深渊副本",
}

assert parse_create_command(
    "起队 10 晚上八点打深渊副本"
) == {
    "action": "create",
    "max_size": 10,
    "description": "晚上八点打深渊副本",
}

# 边界人数
assert parse_create_command("起队 2 两人队") is not None
assert parse_create_command("起队 50 五十人队") is not None

# 非法人数
assert parse_create_command("起队 1 测试") is None
assert parse_create_command("起队 51 测试") is None
assert parse_create_command("起队 abc 测试") is None

# 缺少参数
assert parse_create_command("起队") is None
assert parse_create_command("起队 5") is None

# 其他命令不能被误识别
assert parse_create_command("参加 #001") is None
assert parse_create_command("帮助") is None

assert parse_join_command(
    "参加 #001"
) == {
    "action": "join",
    "party_id": 1,
}

assert parse_join_command(
    "参加 #023"
) == {
    "action": "join",
    "party_id": 23,
}

assert parse_join_command("参加 #1000") == {
    "action": "join",
    "party_id": 1000,
}

# 必须使用 #NNN 格式
assert parse_join_command("参加 001") is None
assert parse_join_command("参加 #1") is None
assert parse_join_command("参加 #000") is None

# 参数数量错误
assert parse_join_command("参加") is None
assert parse_join_command("参加 #001 extra") is None

# 其他命令不能误识别
assert parse_join_command("退出 #001") is None
assert parse_join_command("查看 #001") is None
assert parse_join_command("帮助") is None

assert parse_leave_command(
    "退出 #001"
) == {
    "action": "leave",
    "party_id": 1,
}

assert parse_leave_command(
    "退出 #023"
) == {
    "action": "leave",
    "party_id": 23,
}

assert parse_leave_command("退出 #1000") == {
    "action": "leave",
    "party_id": 1000,
}

# 必须使用 #NNN 格式
assert parse_leave_command("退出 001") is None
assert parse_leave_command("退出 #1") is None
assert parse_leave_command("退出 #000") is None

# 参数数量错误
assert parse_leave_command("退出") is None
assert parse_leave_command("退出 #001 extra") is None

# 其他命令不能误识别
assert parse_leave_command("参加 #001") is None
assert parse_leave_command("查看 #001") is None
assert parse_leave_command("帮助") is None

assert parse_view_command(
    "查看 #001"
) == {
    "action": "view",
    "party_id": 1,
}

assert parse_view_command(
    "查看 #023"
) == {
    "action": "view",
    "party_id": 23,
}

assert parse_view_command("查看 #1000") == {
    "action": "view",
    "party_id": 1000,
}

# 必须使用 #NNN 格式
assert parse_view_command("查看 001") is None
assert parse_view_command("查看 #1") is None
assert parse_view_command("查看 #000") is None

# 参数数量错误
assert parse_view_command("查看") is None
assert parse_view_command("查看 #001 extra") is None

# 其他命令不能误识别
assert parse_view_command("参加 #001") is None
assert parse_view_command("退出 #001") is None
assert parse_view_command("帮助") is None

assert parse_disband_command(
    "解散 #001"
) == {
    "action": "disband",
    "party_id": 1,
}

assert parse_disband_command(
    "解散 #023"
) == {
    "action": "disband",
    "party_id": 23,
}

assert parse_disband_command("解散 #1000") == {
    "action": "disband",
    "party_id": 1000,
}

# 必须使用 #NNN 格式
assert parse_disband_command("解散 001") is None
assert parse_disband_command("解散 #1") is None
assert parse_disband_command("解散 #000") is None

# 参数数量错误
assert parse_disband_command("解散") is None
assert parse_disband_command("解散 #001 extra") is None

# 其他命令不能误识别
assert parse_disband_command("参加 #001") is None
assert parse_disband_command("退出 #001") is None
assert parse_disband_command("查看 #001") is None
assert parse_disband_command("帮助") is None

assert parse_list_command("队伍") == {
    "action": "list",
}

# 前后空格允许
assert parse_list_command(" 队伍 ") == {
    "action": "list",
}

# 不允许额外参数
assert parse_list_command("队伍 #001") is None
assert parse_list_command("队伍 extra") is None

# 其他命令不能误识别
assert parse_list_command("帮助") is None
assert parse_list_command("查看 #001") is None
assert parse_list_command("参加 #001") is None
assert parse_list_command("解散 #001") is None

assert parse_help_command("帮助") == {
    "action": "help",
}

# 前后空格允许
assert parse_help_command(" 帮助 ") == {
    "action": "help",
}

# 不允许额外参数
assert parse_help_command("帮助 extra") is None
assert parse_help_command("帮助 #001") is None

# 其他命令不能误识别
assert parse_help_command("队伍") is None
assert parse_help_command("查看 #001") is None
assert parse_help_command("参加 #001") is None
assert parse_help_command("解散 #001") is None

# unified command parser
assert parse_command("起队 5 晚上刷副本") == {
    "action": "create",
    "max_size": 5,
    "description": "晚上刷副本",
}

assert parse_command("参加 #001") == {
    "action": "join",
    "party_id": 1,
}

assert parse_command("退出 #001") == {
    "action": "leave",
    "party_id": 1,
}

assert parse_command("查看 #001") == {
    "action": "view",
    "party_id": 1,
}

assert parse_command("解散 #001") == {
    "action": "disband",
    "party_id": 1,
}

assert parse_command("队伍") == {
    "action": "list",
}

assert parse_command("帮助") == {
    "action": "help",
}

# unknown / malformed commands
assert parse_command("测试") is None
assert parse_command("参加 001") is None
assert parse_command("起队 1 人数错误") is None
assert parse_command("") is None

print("parser tests passed")

from src.message_formatter import (
    format_party,
    format_party_id,
    format_status,
)


assert format_party_id(1) == "#001"
assert format_party_id(23) == "#023"
assert format_party_id(999) == "#999"
assert format_party_id(1000) == "#1000"

assert format_status("OPEN") == "招募中"
assert format_status("FULL") == "已满"
assert format_status("DISBANDED") == "已解散"
assert format_status("EXPIRED") == "已过期"

# 未知状态保留原值
assert format_status("UNKNOWN") == "UNKNOWN"

party = {
    "party_id": 1,
    "max_size": 5,
    "description": "测试队伍",
    "status": "OPEN",
    "member_count": 2,
}

result = format_party(
    party=party,
    creator_name="大可（奥苏斯）",
    member_names=[
        "大可（奥苏斯）",
        "测试成员",
    ],
)

expected = """队伍 #001
发起人：大可（奥苏斯）
人数：2/5
简介：测试队伍
状态：招募中
成员：
1. 大可（奥苏斯）
2. 测试成员"""

assert result == expected

print("formatter tests passed")

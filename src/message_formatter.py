STATUS_LABELS = {
    "OPEN": "招募中",
    "FULL": "已满",
    "DISBANDED": "已解散",
    "EXPIRED": "已过期",
}


def format_party_id(party_id: int) -> str:
    return f"#{party_id:03d}"


def format_status(status: str) -> str:
    return STATUS_LABELS.get(status, status)

def format_party(
    party: dict,
    creator_name: str,
    member_names: list[str],
) -> str:
    party_label = format_party_id(party["party_id"])
    status_label = format_status(party["status"])

    lines = [
        f"队伍 {party_label}",
        f"发起人：{creator_name}",
        f"人数：{party['member_count']}/{party['max_size']}",
        f"简介：{party['description']}",
        f"状态：{status_label}",
        "成员：",
    ]

    for index, member_name in enumerate(
        member_names,
        start=1,
    ):
        lines.append(
            f"{index}. {member_name}"
        )

    return "\n".join(lines)
from typing import Any


def extract_command(event: dict[str, Any]) -> str | None:
    """
    Extract command text from a QQ group message that explicitly @mentions
    the current bot.

    Returns:
        Command text with surrounding whitespace removed.
        None if this isn't a valid group message directed at the bot.
    """

    if event.get("post_type") != "message":
        return None

    if event.get("message_type") != "group":
        return None

    self_id = str(event.get("self_id", ""))
    message = event.get("message")

    if not self_id or not isinstance(message, list):
        return None

    mentioned_bot = False
    text_parts: list[str] = []

    for segment in message:
        if not isinstance(segment, dict):
            continue

        segment_type = segment.get("type")
        data = segment.get("data", {})

        if segment_type == "at":
            if str(data.get("qq", "")) == self_id:
                mentioned_bot = True

        elif segment_type == "text":
            text_parts.append(str(data.get("text", "")))

    if not mentioned_bot:
        return None

    return "".join(text_parts).strip()


def parse_party_id(value: str) -> int | None:
    """
    Parse a party ID in the required #NNN format.

    Examples:
        #001 -> 1
        #023 -> 23
        #999 -> 999
        #1000 -> 1000

    Invalid:
        001
        1
        #0
        #000
        #abc
        #-1
    """

    if not value.startswith("#"):
        return None

    number = value[1:]

    if not number.isdigit():
        return None

    if len(number) < 3:
        return None

    party_id = int(number)

    if party_id <= 0:
        return None

    return party_id


def parse_create_command(command: str) -> dict | None:
    """
    Parse:
        起队 <人数> <简介>
        起队 <人数> <HH:MM> <简介>

    Examples:
        起队 5 深渊副本
        起队 5 20:30 深渊副本
    """
    command = command.strip()
    if command == "起队":
        return {
            "action":"create_last",
        }

    parts = command.split(maxsplit=3)

    if len(parts) not in (3, 4):
        return None

    action = parts[0]
    size_text = parts[1]

    if action != "起队":
        return None

    if not size_text.isdigit():
        return None

    max_size = int(size_text)

    if not 2 <= max_size <= 50:
        return None

    start_time = None

    if len(parts) == 3:
        description = parts[2]
    else:
        time_text = parts[2]
        description = parts[3]

        time_parts = time_text.split(":")

        if len(time_parts) != 2:
            return None

        hour_text, minute_text = time_parts

        if not (
            hour_text.isdigit()
            and minute_text.isdigit()
        ):
            return None

        hour = int(hour_text)
        minute = int(minute_text)

        if not (
            0 <= hour <= 23
            and 0 <= minute <= 59
        ):
            return None

        start_time = f"{hour:02d}:{minute:02d}"

    description = description.strip()

    if not 1 <= len(description) <= 100:
        return None

    return {
        "action": "create",
        "max_size": max_size,
        "description": description,
        "start_time": start_time,
    }


def parse_join_command(command: str) -> dict | None:
    """
    Parse:
        参加 #ID

    Example:
        参加 #001
    """

    parts = command.split()

    if len(parts) != 2:
        return None

    action, party_text = parts

    if action != "参加":
        return None

    party_id = parse_party_id(party_text)

    if party_id is None:
        return None

    return {
        "action": "join",
        "party_id": party_id,
    }


def parse_leave_command(command: str) -> dict | None:
    """
    Parse:
        退出 #ID

    Example:
        退出 #001
    """

    parts = command.split()

    if len(parts) != 2:
        return None

    action, party_text = parts

    if action != "退出":
        return None

    party_id = parse_party_id(party_text)

    if party_id is None:
        return None

    return {
        "action": "leave",
        "party_id": party_id,
    }


def parse_view_command(command: str) -> dict | None:
    """
    Parse:
        查看 #ID

    Example:
        查看 #001
    """

    parts = command.split()

    if len(parts) != 2:
        return None

    action, party_text = parts

    if action != "查看":
        return None

    party_id = parse_party_id(party_text)

    if party_id is None:
        return None

    return {
        "action": "view",
        "party_id": party_id,
    }


def parse_disband_command(command: str) -> dict | None:
    """
    Parse:
        解散 #ID

    Example:
        解散 #001
    """

    parts = command.split()

    if len(parts) != 2:
        return None

    action, party_text = parts

    if action != "解散":
        return None

    party_id = parse_party_id(party_text)

    if party_id is None:
        return None

    return {
        "action": "disband",
        "party_id": party_id,
    }


def parse_list_command(command: str) -> dict | None:
    """
    Parse:
        队伍
    """

    if command.strip() != "队伍":
        return None

    return {
        "action": "list",
    }


def parse_help_command(command: str) -> dict | None:
    """
    Parse:
        帮助
    """

    if command.strip() != "帮助":
        return None

    return {
        "action": "help",
    }


def parse_command(command: str) -> dict | None:
    """
    Parse any supported bot command.
    """

    parsers = (
        parse_create_command,
        parse_join_command,
        parse_leave_command,
        parse_view_command,
        parse_disband_command,
        parse_list_command,
        parse_help_command,
    )

    for parser in parsers:
        result = parser(command)

        if result is not None:
            return result

    return None

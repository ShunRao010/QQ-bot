import asyncio
import time

from src.message_formatter import format_party
from src.message_parser import extract_command, parse_command
from src.onebot_client import OneBotClient

from src.database import (
    create_party,
    disband_party,
    get_party,
    handle_group_member_leave,
    initialize_database,
    join_party,
    leave_party,
    list_active_parties,
)

ALLOWED_GROUP_IDS = {
    106394179,
}

HELP_TEXT = """组队Bot命令：

@Bot 起队 <人数> <简介>
@Bot 参加 #ID
@Bot 退出 #ID
@Bot 查看 #ID
@Bot 队伍
@Bot 解散 #ID
@Bot 帮助

规则：
- 所有命令必须 @Bot
- 命令与参数之间必须有空格
- 队伍编号必须使用 #001、#002 这样的格式
- 队伍人数范围为 2–50 人
- 创建者自动加入并占 1 个位置
- 同一成员可以参加多个队伍
- 队伍满员后不能继续加入
- 创建者不能直接退出自己的队伍，需要解散队伍
- 队伍创建后 6 小时自动过期
- 已解散和已过期队伍不会出现在“队伍”列表中
"""

ERROR_MESSAGES = {
    "PARTY_NOT_FOUND": "队伍不存在。",
    "PARTY_EXPIRED": "该队伍已过期。",
    "PARTY_DISBANDED": "该队伍已解散。",
    "ALREADY_MEMBER": "你已经在这个队伍中。",
    "PARTY_FULL": "该队伍已满。",
    "NOT_MEMBER": "你不在这个队伍中。",
    "CREATOR_CANNOT_LEAVE": "发起人不能退出自己的队伍，请使用“解散 #ID”。",
    "NO_PERMISSION": "你没有权限解散这个队伍。",
}
def get_error_message(exc: ValueError) -> str:
    error_code = str(exc)

    return ERROR_MESSAGES.get(
        error_code,
        "操作失败，请稍后重试。",
    )
    
async def run_bot(client: OneBotClient) -> None:
    while True:
        event = await client.receive_event()

        if event.get("_internal") == "disconnected":
            raise ConnectionError(
                event.get(
                    "error",
                    "OneBot WebSocket disconnected",
                )
            )
        group_id = event.get("group_id")
        
        if group_id not in ALLOWED_GROUP_IDS:
            continue
        
        if (
            event.get("post_type") == "notice"
            and event.get("notice_type") == "group_decrease"
        ):
            user_id = event.get("user_id")

            if not isinstance(group_id, int):
                continue

            if not isinstance(user_id, int):
                continue

            # Bot 自己离群时不处理队伍数据
            if user_id == event.get("self_id"):
                continue

            now = int(time.time())

            handle_group_member_leave(
                group_id=group_id,
                user_id=user_id,
                now=now,
            )

            print(
                f"group member left: "
                f"group={group_id} "
                f"user={user_id} "
                f"sub_type={event.get('sub_type')!r}"
            )

            continue
        command_text = extract_command(event)

        if command_text is None:
            continue
        command = parse_command(command_text)

        print(
            f"group={event.get('group_id')} "
            f"user={event.get('user_id')} "
            f"command_text={command_text!r} "
            f"parsed={command!r}"
        )

        if command is None:
            group_id = event.get("group_id")

            if isinstance(group_id, int):
                await client.send_group_message(
                    group_id=group_id,
                    message="命令格式错误，请发送“@Bot 帮助”查看正确格式。",
                )

            continue

        if command["action"] == "create":
            group_id = event.get("group_id")
            creator_id = event.get("user_id")

            if not isinstance(group_id, int):
                continue

            if not isinstance(creator_id, int):
                continue

            party_id = create_party(
                group_id=group_id,
                creator_id=creator_id,
                max_size=command["max_size"],
                description=command["description"],
                created_at=int(time.time()),
            )

            print(
                f"created party=#{party_id:03d} "
                f"group={group_id} "
                f"creator={creator_id}"
            )

            party = get_party(
                group_id=group_id,
                party_id=party_id,
                now=int(time.time()),
            )
            print("party:", party)
            
            if party is None:
                continue

            creator_name = await client.get_group_member_display_name(
                group_id=group_id,
                user_id=creator_id,
            )

            print(f"creator_name={creator_name!r}")
            
            member_names = []

            for member in party["members"]:
                member_name = await client.get_group_member_display_name(
                    group_id=group_id,
                    user_id=member["user_id"],
                )

                member_names.append(member_name)

            print(f"member_names={member_names!r}")
            
            party_message = format_party(
                party=party,
                creator_name=creator_name,
                member_names=member_names,
            )

            print("party_message:")
            print(party_message)
            
            response = await client.send_group_message(
                group_id=group_id,
                message=party_message,
            )

            print(
                "send_group_msg:",
                response.get("status"),
                response.get("retcode"),
            )
            
            continue

        if command["action"] == "join":
            group_id = event.get("group_id")
            user_id = event.get("user_id")

            if not isinstance(group_id, int):
                continue

            if not isinstance(user_id, int):
                continue

            now = int(time.time())

            try:
                join_party(
                    group_id=group_id,
                    party_id=command["party_id"],
                    user_id=user_id,
                    now=now,
                )
            except ValueError as exc:
                print(
                    f"join_party failed: "
                    f"party=#{command['party_id']:03d} "
                    f"user={user_id} "
                    f"error={exc}"
                )
                await client.send_group_message(
                    group_id=group_id,
                    message=get_error_message(exc),
                )
                continue

            print(
                f"joined party=#{command['party_id']:03d} "
                f"group={group_id} "
                f"user={user_id}"
            )

            party = get_party(
                group_id=group_id,
                party_id=command["party_id"],
                now=now,
            )
            
            print("party after join:", party)
            
            if party is None:
                continue

            creator_name = await client.get_group_member_display_name(
                group_id=group_id,
                user_id=party["creator_id"],
            )

            member_names = []

            for member in party["members"]:
                member_name = await client.get_group_member_display_name(
                    group_id=group_id,
                    user_id=member["user_id"],
                )
                member_names.append(member_name)

            party_message = format_party(
                party=party,
                creator_name=creator_name,
                member_names=member_names,
            )

            response = await client.send_group_message(
                group_id=group_id,
                message=party_message,
            )

            print(
                "join send_group_msg:",
                response.get("status"),
                response.get("retcode"),
            )
            
            continue
        
        if command["action"] == "leave":
            group_id = event.get("group_id")
            user_id = event.get("user_id")

            if not isinstance(group_id, int):
                continue

            if not isinstance(user_id, int):
                continue

            now = int(time.time())

            try:
                leave_party(
                    group_id=group_id,
                    party_id=command["party_id"],
                    user_id=user_id,
                    now=now,
                )

            except ValueError as exc:
                print(
                    f"leave_party failed: "
                    f"party=#{command['party_id']:03d} "
                    f"user={user_id} "
                    f"error={exc}"
                )
                await client.send_group_message(
                    group_id=group_id,
                    message=get_error_message(exc),
                )
                continue

            print(
                f"left party=#{command['party_id']:03d} "
                f"group={group_id} "
                f"user={user_id}"
            )

            party = get_party(
                group_id=group_id,
                party_id=command["party_id"],
                now=now,
            )

            if party is None:
                continue

            creator_name = await client.get_group_member_display_name(
                group_id=group_id,
                user_id=party["creator_id"],
            )

            member_names = []

            for member in party["members"]:
                member_name = await client.get_group_member_display_name(
                    group_id=group_id,
                    user_id=member["user_id"],
                )
                member_names.append(member_name)

            party_message = format_party(
                party=party,
                creator_name=creator_name,
                member_names=member_names,
            )

            response = await client.send_group_message(
                group_id=group_id,
                message=party_message,
            )

            print(
                "leave send_group_msg:",
                response.get("status"),
                response.get("retcode"),
            )
            
            continue
        
        if command["action"] == "view":
            group_id = event.get("group_id")

            if not isinstance(group_id, int):
                continue

            now = int(time.time())

            party = get_party(
                group_id=group_id,
                party_id=command["party_id"],
                now=now,
            )

            if party is None:
                print(
                    f"view failed: "
                    f"party=#{command['party_id']:03d} "
                    f"error=PARTY_NOT_FOUND"
                )
                await client.send_group_message(
                    group_id=group_id,
                    message=ERROR_MESSAGES["PARTY_NOT_FOUND"],
                )
                continue

            creator_name = await client.get_group_member_display_name(
                group_id=group_id,
                user_id=party["creator_id"],
            )

            member_names = []

            for member in party["members"]:
                member_name = await client.get_group_member_display_name(
                    group_id=group_id,
                    user_id=member["user_id"],
                )
                member_names.append(member_name)

            party_message = format_party(
                party=party,
                creator_name=creator_name,
                member_names=member_names,
            )

            response = await client.send_group_message(
                group_id=group_id,
                message=party_message,
            )

            print(
                "view send_group_msg:",
                response.get("status"),
                response.get("retcode"),
            )

            continue
        
        if command["action"] == "list":
            group_id = event.get("group_id")

            if not isinstance(group_id, int):
                continue

            now = int(time.time())

            parties = list_active_parties(
                group_id=group_id,
                now=now,
            )

            if not parties:
                message = "当前没有正在进行的队伍。"
            else:
                lines = ["当前队伍："]

                for party in parties:
                    status_label = (
                        "已满"
                        if party["status"] == "FULL"
                        else "招募中"
                    )

                    lines.append(
                        f"#{party['party_id']:03d} "
                        f"[{status_label}] "
                        f"{party['member_count']}/{party['max_size']} "
                        f"{party['description']}"
                    )

                message = "\n".join(lines)

            response = await client.send_group_message(
                group_id=group_id,
                message=message,
            )

            print(
                "list send_group_msg:",
                response.get("status"),
                response.get("retcode"),
            )

            continue
        
        if command["action"] == "disband":
            group_id = event.get("group_id")
            user_id = event.get("user_id")

            if not isinstance(group_id, int):
                continue

            if not isinstance(user_id, int):
                continue

            sender = event.get("sender", {})
            role = sender.get("role")

            is_admin = role in {
                "admin",
                "owner",
            }

            now = int(time.time())

            try:
                disband_party(
                    group_id=group_id,
                    party_id=command["party_id"],
                    user_id=user_id,
                    now=now,
                    is_admin=is_admin,
                )

            except ValueError as exc:
                print(
                    f"disband_party failed: "
                    f"party=#{command['party_id']:03d} "
                    f"user={user_id} "
                    f"error={exc}"
                )
                await client.send_group_message(
                    group_id=group_id,
                    message=get_error_message(exc),
                )
                continue

            print(
                f"disbanded party=#{command['party_id']:03d} "
                f"group={group_id} "
                f"user={user_id} "
                f"is_admin={is_admin}"
            )

            party = get_party(
                group_id=group_id,
                party_id=command["party_id"],
                now=now,
            )

            if party is None:
                continue

            creator_name = await client.get_group_member_display_name(
                group_id=group_id,
                user_id=party["creator_id"],
            )

            member_names = []

            for member in party["members"]:
                member_name = await client.get_group_member_display_name(
                    group_id=group_id,
                    user_id=member["user_id"],
                )
                member_names.append(member_name)

            party_message = format_party(
                party=party,
                creator_name=creator_name,
                member_names=member_names,
            )

            response = await client.send_group_message(
                group_id=group_id,
                message=party_message,
            )

            print(
                "disband send_group_msg:",
                response.get("status"),
                response.get("retcode"),
            )
            
            continue
        
        if command["action"] != "help":
            continue

        group_id = event.get("group_id")

        if not isinstance(group_id, int):
            continue

        response = await client.send_group_message(
            group_id,
            HELP_TEXT,
        )

        print(
            "send_group_msg:",
            response.get("status"),
            response.get("retcode"),
        )

async def main() -> None:
    initialize_database()

    reconnect_delay = 1

    while True:
        client = OneBotClient()

        try:
            print("Connecting to OneBot...")
            await client.connect()

            print("Bot connected.")
            reconnect_delay = 1

            await run_bot(client)

        except asyncio.CancelledError:
            # systemd stop / task cancellation：
            # 正常退出，不进入自动重连。
            raise

        except KeyboardInterrupt:
            # 手动 Ctrl+C：
            # 正常退出，不进入自动重连。
            raise

        except Exception as exc:
            print(
                f"Bot connection lost: {exc!r}. "
                f"Reconnecting in {reconnect_delay}s..."
            )

            await asyncio.sleep(reconnect_delay)

            reconnect_delay = min(
                reconnect_delay * 2,
                30,
            )

        finally:
            try:
                await client.close()
            except Exception as exc:
                print(
                    f"Error while closing OneBot client: {exc!r}"
                )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")



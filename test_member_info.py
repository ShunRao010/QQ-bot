import asyncio

from src.onebot_client import OneBotClient


GROUP_ID = 106394179
USER_ID = 1589561488


async def main() -> None:
    client = OneBotClient()

    try:
        await client.connect()

        display_name = await client.get_group_member_display_name(
            GROUP_ID,
            USER_ID,
        )

        print(f"display_name={display_name!r}")

    finally:
        await client.close()


asyncio.run(main())

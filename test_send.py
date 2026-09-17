import asyncio

from src.onebot_client import OneBotClient


GROUP_ID = 106394179


async def main():
    client = OneBotClient()

    try:
        await client.connect()
        print("Connected.")

        response = await client.send_group_message(
            GROUP_ID,
            "QQ组队Bot连接测试 2",
        )

        print("Response:")
        print(response)

    finally:
        await client.close()


asyncio.run(main())

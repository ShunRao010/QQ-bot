import asyncio
import os

import websockets


async def main():
    token = os.environ["NAPCAT_TOKEN"]

    async with websockets.connect(
        "ws://127.0.0.1:3001",
        additional_headers={
            "Authorization": f"Bearer {token}",
        },
    ) as ws:
        print("Connected to NapCat OneBot WebSocket.")

        while True:
            message = await ws.recv()
            print(message)


asyncio.run(main())

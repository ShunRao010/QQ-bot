import asyncio
import json
import os
import uuid
from typing import Any

import websockets


class OneBotClient:
    def __init__(self) -> None:
        self.url = "ws://127.0.0.1:3001"
        self.token = os.environ["NAPCAT_TOKEN"]

        self.ws = None

        self.pending: dict[str, asyncio.Future] = {}
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        self.reader_task: asyncio.Task | None = None

    async def connect(self) -> None:
        self.ws = await websockets.connect(
            self.url,
            additional_headers={
                "Authorization": f"Bearer {self.token}",
            },
        )

        self.reader_task = asyncio.create_task(
            self._reader_loop()
        )

    async def _reader_loop(self) -> None:
        if self.ws is None:
            raise RuntimeError("OneBot WebSocket is not connected")

        disconnect_error: Exception | None = None

        try:
            async for raw in self.ws:
                data = json.loads(raw)

                echo = data.get("echo")

                if echo is not None:
                    future = self.pending.get(str(echo))

                    if future is not None and not future.done():
                        future.set_result(data)

                    continue

                await self.events.put(data)

        except Exception as exc:
            disconnect_error = exc

        finally:
            # 让所有正在等待的 API 请求立即失败
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(
                        ConnectionError(
                            "OneBot WebSocket disconnected"
                        )
                    )

            await self.events.put(
                {
                    "_internal": "disconnected",
                    "error": (
                        repr(disconnect_error)
                        if disconnect_error is not None
                        else "WebSocket closed"
                    ),
                }
            )

    async def receive_event(self) -> dict[str, Any]:
        return await self.events.get()

    async def call_action(
        self,
        action: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("OneBot WebSocket is not connected")

        echo = str(uuid.uuid4())

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self.pending[echo] = future

        request = {
            "action": action,
            "params": params,
            "echo": echo,
        }

        try:
            await self.ws.send(
                json.dumps(request, ensure_ascii=False)
            )

            return await asyncio.wait_for(
                future,
                timeout=10,
            )

        finally:
            self.pending.pop(echo, None)
    
    async def get_group_member_info(
        self,
        group_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        return await self.call_action(
            "get_group_member_info",
            {
                "group_id": group_id,
                "user_id": user_id,
                "no_cache": True,
            },
        )

    async def can_at_all(
        self,
        group_id: int,
    ) -> bool:
        try:
            response = await self.get_group_at_all_remain(
                group_id
            )
        except Exception:
            return False

        if response.get("status") != "ok":
            return False

        data = response.get("data")

        if not isinstance(data, dict):
            return False

        if not data.get("can_at_all", False):
            return False

        group_remain = data.get(
            "remain_at_all_count_for_group",
            0,
        )

        user_remain = data.get(
            "remain_at_all_count_for_uin",
            0,
        )

        return (
            isinstance(group_remain, int)
            and isinstance(user_remain, int)
            and group_remain > 0
            and user_remain > 0
        )

    async def get_group_at_all_remain(
        self,
        group_id: int,
    ) -> dict[str, Any]:
        return await self.call_action(
            "get_group_at_all_remain",
            {
                "group_id": group_id,
            },
        )
    
    async def get_group_member_display_name(
        self,
        group_id: int,
        user_id: int,
    ) -> str:
        response = await self.get_group_member_info(
            group_id,
            user_id,
        )

        if response.get("status") != "ok":
            return str(user_id)

        data = response.get("data", {})

        card = str(data.get("card", "")).strip()
        nickname = str(data.get("nickname", "")).strip()

        if card:
            return card

        if nickname:
            return nickname

        return str(user_id)
    
    async def send_group_message(
        self,
        group_id: int,
        message: str | list[dict[str,Any]],
    ) -> dict[str, Any]:
        if self.ws is None:
            raise RuntimeError("OneBot WebSocket is not connected")

        echo = str(uuid.uuid4())

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self.pending[echo] = future

        request = {
            "action": "send_group_msg",
            "params": {
                "group_id": group_id,
                "message": message,
            },
            "echo": echo,
        }

        try:
            await self.ws.send(
                json.dumps(request, ensure_ascii=False)
            )

            return await asyncio.wait_for(
                future,
                timeout=10,
            )

        finally:
            self.pending.pop(echo, None)

    async def close(self) -> None:
        if self.reader_task is not None:
            self.reader_task.cancel()

            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass

        if self.ws is not None:
            await self.ws.close()

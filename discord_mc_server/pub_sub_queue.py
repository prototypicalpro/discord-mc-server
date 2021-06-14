import asyncio
from weakref import WeakSet
from typing import Generic, TypeVar

WorkItem = TypeVar('WorkItem')


class PubSubQueue(Generic[WorkItem]):
    def __init__(self):
        self._listeners: WeakSet['asyncio.Queue[WorkItem]'] = WeakSet()

    def subscribe(self) -> 'asyncio.Queue[WorkItem]':
        queue = asyncio.Queue()
        self._listeners.add(queue)
        return queue

    async def publish(self, item: WorkItem):
        for queue in self._listeners:
            await queue.put(item)

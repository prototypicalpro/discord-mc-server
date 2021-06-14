import asyncio
import pytest
import gc

from discord_mc_server.pub_sub_queue import PubSubQueue


@pytest.mark.asyncio
async def test_publishes_no_listeners():
    queue = PubSubQueue()
    await queue.publish('hello!')


@pytest.mark.asyncio
async def test_publishes_to_one_listener():
    queue = PubSubQueue()
    sub1 = queue.subscribe()

    res = await asyncio.gather(queue.publish('hello!'), sub1.get())
    assert res[1] == 'hello!'
    sub1.task_done()
    assert sub1.empty()

    res = await asyncio.gather(queue.publish('hello again!'), sub1.get())
    assert res[1] == 'hello again!'
    sub1.task_done()
    assert sub1.empty()


@pytest.mark.asyncio
async def test_publishes_queues_in_order():
    queue = PubSubQueue()
    sub1 = queue.subscribe()

    await queue.publish('hello!')
    await queue.publish('hello again!'),

    assert await sub1.get() == 'hello!'
    assert await sub1.get() == 'hello again!'
    assert sub1.empty()


@pytest.mark.asyncio
async def test_publishes_to_many_listeners():
    queue = PubSubQueue()
    arr = [queue.subscribe() for _ in range(100)]

    res = await asyncio.gather(queue.publish('hello!'), *[r.get() for r in arr])
    assert [r == 'hello!' for r in res[1:]]
    for r in arr:
        r.task_done()
        assert r.empty()


@pytest.mark.asyncio
async def test_publishes_to_late_listeners():
    queue = PubSubQueue()
    sub1 = queue.subscribe()
    sub2 = queue.subscribe()
    sub3 = queue.subscribe()

    res = await asyncio.gather(queue.publish('hello!'), sub1.get())
    assert res[1] == 'hello!'
    sub1.task_done()
    assert sub1.empty()

    res = await asyncio.gather(queue.publish('hello again!'), sub1.get(), sub2.get())
    assert res[1:] == ['hello again!', 'hello!']
    sub1.task_done()
    sub2.task_done()
    assert sub1.empty()

    res = await asyncio.gather(queue.publish('hello final!'), sub1.get(), sub2.get(), sub3.get())
    assert res[1:] == ['hello final!', 'hello again!', 'hello!']
    sub1.task_done()
    sub2.task_done()
    sub3.task_done()
    assert sub1.empty()

    res = await asyncio.gather(sub2.get(), sub3.get())
    assert res == ['hello final!', 'hello again!']
    sub2.task_done()
    sub3.task_done()
    assert sub2.empty()

    res = await sub3.get()
    assert res == 'hello final!'
    assert sub3.empty()


@pytest.mark.asyncio
async def test_evicts_old_listeners():
    queue = PubSubQueue()
    sub1 = queue.subscribe()
    assert sub1 in queue._listeners

    del sub1
    gc.collect()

    assert not len(queue._listeners)

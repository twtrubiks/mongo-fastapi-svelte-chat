"""並發操作的完整測試"""

import asyncio
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest


class TestConcurrentOperations:
    """測試各種並發場景"""

    @pytest.mark.asyncio
    async def test_concurrent_database_writes(self):
        """測試並發資料庫寫入"""

        # Mock 資料庫
        class ConcurrentDatabase:
            def __init__(self):
                self.data = {}
                self.lock = asyncio.Lock()
                self.write_count = 0

            async def write(self, key, value):
                async with self.lock:
                    # 模擬寫入延遲
                    await asyncio.sleep(0.01)
                    self.data[key] = value
                    self.write_count += 1
                    return True

            async def read(self, key):
                async with self.lock:
                    return self.data.get(key)

        db = ConcurrentDatabase()

        # 並發寫入 100 個項目
        async def write_item(i):
            await db.write(f"key_{i}", f"value_{i}")

        # 執行並發寫入
        await asyncio.gather(*[write_item(i) for i in range(100)])

        # 驗證所有寫入都成功
        assert db.write_count == 100
        assert len(db.data) == 100

        # 驗證數據完整性
        for i in range(100):
            value = await db.read(f"key_{i}")
            assert value == f"value_{i}"

    @pytest.mark.asyncio
    async def test_race_condition_prevention(self):
        """測試競態條件預防"""

        # 模擬帳戶餘額操作
        class BankAccount:
            def __init__(self, initial_balance):
                self.balance = initial_balance
                self.lock = asyncio.Lock()
                self.transaction_log = []

            async def withdraw(self, amount):
                async with self.lock:
                    if self.balance >= amount:
                        # 模擬處理延遲
                        await asyncio.sleep(0.001)
                        self.balance -= amount
                        self.transaction_log.append(("withdraw", amount))
                        return True
                    return False

            async def deposit(self, amount):
                async with self.lock:
                    await asyncio.sleep(0.001)
                    self.balance += amount
                    self.transaction_log.append(("deposit", amount))
                    return True

        account = BankAccount(1000)

        # 並發執行存款和提款
        async def random_transaction():
            operation = random.choice(["deposit", "withdraw"])
            amount = random.randint(10, 100)

            if operation == "deposit":
                await account.deposit(amount)
            else:
                await account.withdraw(amount)

        # 執行 50 個並發交易
        await asyncio.gather(*[random_transaction() for _ in range(50)])

        # 計算預期餘額
        expected_balance = 1000
        for op, amount in account.transaction_log:
            if op == "deposit":
                expected_balance += amount
            elif op == "withdraw":
                expected_balance -= amount

        # 驗證餘額正確（沒有競態條件）
        assert account.balance == expected_balance

    @pytest.mark.asyncio
    async def test_connection_pool_management(self):
        """測試連接池管理"""

        # Mock 連接池
        class ConnectionPool:
            def __init__(self, max_connections=10):
                self.max_connections = max_connections
                self.available_connections = asyncio.Queue(maxsize=max_connections)
                self.in_use = set()
                self.created_count = 0

                # 預先創建連接
                for i in range(max_connections):
                    conn = Mock(id=i)
                    self.available_connections.put_nowait(conn)
                    self.created_count += 1

            async def acquire(self):
                try:
                    # 等待可用連接
                    conn = await asyncio.wait_for(
                        self.available_connections.get(), timeout=5.0
                    )
                    self.in_use.add(conn)
                    return conn
                except TimeoutError as e:
                    raise Exception("Connection pool exhausted") from e

            async def release(self, conn):
                if conn in self.in_use:
                    self.in_use.remove(conn)
                    await self.available_connections.put(conn)

        pool = ConnectionPool(max_connections=5)

        # 測試並發連接請求
        async def use_connection(duration):
            conn = await pool.acquire()
            try:
                # 模擬使用連接
                await asyncio.sleep(duration)
                return f"Used connection {conn.id}"
            finally:
                await pool.release(conn)

        # 並發使用連接（超過池大小）
        tasks = [use_connection(0.1) for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # 驗證所有請求都完成
        assert len(results) == 20
        assert all("Used connection" in r for r in results)

        # 驗證沒有創建額外的連接
        assert pool.created_count == 5

    @pytest.mark.asyncio
    async def test_distributed_locking(self):
        """測試分散式鎖"""

        # Mock 分散式鎖
        class DistributedLock:
            def __init__(self):
                self.locks = {}
                self.lock_mutex = asyncio.Lock()

            async def acquire(self, key, timeout=30):
                async with self.lock_mutex:
                    if key in self.locks:
                        return False

                    self.locks[key] = {
                        "owner": id(asyncio.current_task()),
                        "acquired_at": time.time(),
                        "timeout": timeout,
                    }
                    return True

            async def release(self, key):
                async with self.lock_mutex:
                    if key in self.locks:
                        current_task_id = id(asyncio.current_task())
                        if self.locks[key]["owner"] == current_task_id:
                            del self.locks[key]
                            return True
                    return False

        lock_manager = DistributedLock()
        results = []

        # 測試互斥訪問
        async def critical_section(worker_id):
            acquired = await lock_manager.acquire("resource_1")
            if acquired:
                try:
                    # 臨界區
                    results.append(f"Worker {worker_id} entered")
                    await asyncio.sleep(0.05)
                    results.append(f"Worker {worker_id} exited")
                finally:
                    await lock_manager.release("resource_1")
            else:
                results.append(f"Worker {worker_id} failed to acquire lock")

        # 5 個工作者嘗試獲取同一個鎖
        await asyncio.gather(*[critical_section(i) for i in range(5)])

        # 驗證只有一個工作者成功進入臨界區
        entered_count = sum(1 for r in results if "entered" in r)
        assert entered_count == 1

    @pytest.mark.asyncio
    async def test_message_queue_processing(self):
        """測試訊息佇列處理"""

        # Mock 訊息佇列
        class MessageQueue:
            def __init__(self):
                self.queue = asyncio.Queue()
                self.processed_messages = []
                self.processing_times = []

            async def publish(self, message):
                await self.queue.put(message)

            async def consume(self, worker_id):
                while True:
                    try:
                        message = await asyncio.wait_for(self.queue.get(), timeout=0.1)

                        # 處理訊息
                        start_time = time.time()
                        await asyncio.sleep(random.uniform(0.01, 0.05))

                        self.processed_messages.append(
                            {
                                "message": message,
                                "worker": worker_id,
                                "timestamp": datetime.now(UTC),
                            }
                        )

                        self.processing_times.append(time.time() - start_time)

                    except TimeoutError:
                        break

        mq = MessageQueue()

        # 發布訊息
        publish_tasks = [mq.publish(f"Message {i}") for i in range(50)]
        await asyncio.gather(*publish_tasks)

        # 啟動多個消費者
        consumer_tasks = [mq.consume(worker_id=i) for i in range(5)]
        await asyncio.gather(*consumer_tasks)

        # 驗證所有訊息都被處理
        assert len(mq.processed_messages) == 50

        # 驗證負載均衡（每個工作者都處理了一些訊息）
        worker_counts = {}
        for msg in mq.processed_messages:
            worker = msg["worker"]
            worker_counts[worker] = worker_counts.get(worker, 0) + 1

        # 每個工作者至少處理了一些訊息
        assert all(count > 0 for count in worker_counts.values())

    @pytest.mark.asyncio
    async def test_batch_processing_optimization(self):
        """測試批次處理優化"""

        # 批次處理器
        class BatchProcessor:
            def __init__(self, batch_size=10, timeout=0.1):
                self.batch_size = batch_size
                self.timeout = timeout
                self.pending_items = []
                self.processed_batches = []
                self.lock = asyncio.Lock()

            async def add_item(self, item):
                async with self.lock:
                    self.pending_items.append(item)

                    # 如果達到批次大小，立即處理
                    if len(self.pending_items) >= self.batch_size:
                        await self._process_batch()

            async def _process_batch(self):
                if not self.pending_items:
                    return

                batch = self.pending_items[: self.batch_size]
                self.pending_items = self.pending_items[self.batch_size :]

                # 模擬批次處理
                await asyncio.sleep(0.02)
                self.processed_batches.append(batch)

            async def flush(self):
                async with self.lock:
                    while self.pending_items:
                        await self._process_batch()

        processor = BatchProcessor(batch_size=10)

        # 並發添加項目
        async def add_items(start, count):
            for i in range(start, start + count):
                await processor.add_item(f"Item {i}")

        # 10 個並發生產者，每個添加 10 個項目
        tasks = [add_items(i * 10, 10) for i in range(10)]
        await asyncio.gather(*tasks)

        # 刷新剩餘項目
        await processor.flush()

        # 驗證所有項目都被處理
        total_processed = sum(len(batch) for batch in processor.processed_batches)
        assert total_processed == 100

        # 驗證批次優化（大部分是完整批次）
        full_batches = sum(
            1 for batch in processor.processed_batches if len(batch) == 10
        )
        assert full_batches >= 9  # 至少 9 個完整批次

    def test_thread_safe_operations(self):
        """測試線程安全操作"""

        # 線程安全計數器
        class ThreadSafeCounter:
            def __init__(self):
                self.count = 0
                self.lock = threading.Lock()

            def increment(self):
                with self.lock:
                    current = self.count
                    # 模擬一些處理
                    time.sleep(0.0001)
                    self.count = current + 1

        counter = ThreadSafeCounter()

        # 使用線程池並發增加計數器
        def increment_many(n):
            for _ in range(n):
                counter.increment()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(increment_many, 100) for _ in range(10)]

            # 等待所有線程完成
            for future in as_completed(futures):
                future.result()

        # 驗證計數正確（沒有競態條件）
        assert counter.count == 1000

    @pytest.mark.asyncio
    async def test_semaphore_resource_limiting(self):
        """測試信號量資源限制"""

        # 資源管理器
        class ResourceManager:
            def __init__(self, max_concurrent=3):
                self.semaphore = asyncio.Semaphore(max_concurrent)
                self.active_tasks = 0
                self.max_active = 0
                self.completed_tasks = []

            async def use_resource(self, task_id, duration):
                async with self.semaphore:
                    self.active_tasks += 1
                    self.max_active = max(self.max_active, self.active_tasks)

                    try:
                        # 使用資源
                        await asyncio.sleep(duration)
                        self.completed_tasks.append(task_id)
                    finally:
                        self.active_tasks -= 1

        manager = ResourceManager(max_concurrent=3)

        # 創建 10 個任務，但只允許 3 個並發
        tasks = [manager.use_resource(i, 0.1) for i in range(10)]

        await asyncio.gather(*tasks)

        # 驗證資源限制
        assert manager.max_active <= 3
        assert len(manager.completed_tasks) == 10

    @pytest.mark.asyncio
    async def test_async_context_manager_concurrency(self):
        """測試異步上下文管理器的並發使用"""

        # 異步資源管理器
        class AsyncResource:
            def __init__(self):
                self.in_use = False
                self.use_count = 0
                self.lock = asyncio.Lock()

            async def __aenter__(self):
                async with self.lock:
                    if self.in_use:
                        raise Exception("Resource already in use")
                    self.in_use = True
                    self.use_count += 1
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                async with self.lock:
                    self.in_use = False

            async def do_work(self):
                await asyncio.sleep(0.05)
                return f"Work done #{self.use_count}"

        resource = AsyncResource()
        results = []
        errors = []

        # 並發嘗試使用資源
        async def use_resource(worker_id):
            try:
                async with resource:
                    result = await resource.do_work()
                    results.append(result)
            except Exception as e:
                errors.append(str(e))

        # 5 個工作者嘗試同時使用資源
        await asyncio.gather(*[use_resource(i) for i in range(5)])

        # 驗證資源保護工作正常
        assert len(results) == 1  # 只有一個成功
        assert len(errors) == 4  # 其他都失敗
        assert all("already in use" in e for e in errors)

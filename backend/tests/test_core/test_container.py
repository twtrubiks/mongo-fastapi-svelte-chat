"""
測試依賴注入容器
使用 Mock 優先的方式測試所有功能
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from app.core.container import (
    DIContainer,
    ServiceDescriptor,
    ServiceLifetime,
    get_container,
)


class TestServiceDescriptor:
    """測試服務描述符"""

    def test_service_descriptor_with_implementation_type(self):
        """測試使用實現類型創建服務描述符"""
        descriptor = ServiceDescriptor(
            service_type=Mock,
            implementation_type=MagicMock,
            lifetime=ServiceLifetime.SINGLETON,
        )

        assert descriptor.service_type == Mock
        assert descriptor.implementation_type == MagicMock
        assert descriptor.factory is None
        assert descriptor.instance is None
        assert descriptor.lifetime == ServiceLifetime.SINGLETON

    def test_service_descriptor_with_factory(self):
        """測試使用工廠函數創建服務描述符"""
        factory = Mock()
        descriptor = ServiceDescriptor(
            service_type=Mock, factory=factory, lifetime=ServiceLifetime.SCOPED
        )

        assert descriptor.service_type == Mock
        assert descriptor.implementation_type is None
        assert descriptor.factory == factory
        assert descriptor.instance is None
        assert descriptor.lifetime == ServiceLifetime.SCOPED

    def test_service_descriptor_with_instance(self):
        """測試使用實例創建服務描述符"""
        instance = Mock()
        descriptor = ServiceDescriptor(
            service_type=Mock, instance=instance, lifetime=ServiceLifetime.TRANSIENT
        )

        assert descriptor.service_type == Mock
        assert descriptor.implementation_type is None
        assert descriptor.factory is None
        assert descriptor.instance == instance
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT

    def test_service_descriptor_validation_error(self):
        """測試服務描述符驗證錯誤"""
        # 沒有提供任何實現方式
        with pytest.raises(ValueError) as exc_info:
            ServiceDescriptor(service_type=Mock)
        assert "必須提供" in str(exc_info.value)

        # 提供多個實現方式
        with pytest.raises(ValueError) as exc_info:
            ServiceDescriptor(
                service_type=Mock, implementation_type=MagicMock, factory=Mock()
            )
        assert "必須提供" in str(exc_info.value)


class TestDIContainer:
    """測試依賴注入容器"""

    def test_register_singleton(self):
        """測試註冊單例服務"""
        container = DIContainer()

        # 測試各種註冊方式
        # 1. 使用實現類型
        result = container.register_singleton(Mock, implementation_type=MagicMock)
        assert result == container  # 支援鏈式調用
        assert container.is_registered(Mock)

        # 2. 使用工廠函數
        class Service2:
            pass

        factory = Mock()
        container.register_singleton(Service2, factory=factory)
        assert container.is_registered(Service2)

        # 3. 使用實例
        class Service3:
            pass

        instance = Mock()
        container.register_singleton(Service3, instance=instance)
        assert container.is_registered(Service3)

    def test_register_scoped(self):
        """測試註冊作用域服務"""
        container = DIContainer()

        # 使用實現類型
        result = container.register_scoped(Mock, implementation_type=MagicMock)
        assert result == container
        assert container.is_registered(Mock)

        # 使用工廠函數
        class Service2:
            pass

        factory = Mock()
        container.register_scoped(Service2, factory=factory)
        assert container.is_registered(Service2)

    def test_register_transient(self):
        """測試註冊瞬時服務"""
        container = DIContainer()

        # 使用實現類型
        result = container.register_transient(Mock, implementation_type=MagicMock)
        assert result == container
        assert container.is_registered(Mock)

        # 使用工廠函數
        class Service2:
            pass

        factory = Mock()
        container.register_transient(Service2, factory=factory)
        assert container.is_registered(Service2)

    @pytest.mark.asyncio
    async def test_get_singleton_service(self):
        """測試獲取單例服務"""
        container = DIContainer()

        # 註冊單例服務（使用實例）
        instance = Mock()
        container.register_singleton(Mock, instance=instance)

        # 多次獲取應該返回相同實例
        result1 = await container.get(Mock)
        result2 = await container.get(Mock)

        assert result1 == instance
        assert result2 == instance
        assert result1 is result2

    @pytest.mark.asyncio
    async def test_get_singleton_with_factory(self):
        """測試使用工廠函數的單例服務"""
        container = DIContainer()

        # Mock 工廠函數
        factory = AsyncMock(return_value=Mock())
        container.register_singleton(Mock, factory=factory)

        # 多次獲取
        result1 = await container.get(Mock)
        result2 = await container.get(Mock)

        # 工廠函數只應被調用一次
        factory.assert_called_once()
        assert result1 is result2

    @pytest.mark.asyncio
    async def test_get_scoped_service(self):
        """測試獲取作用域服務"""
        container = DIContainer()

        # 註冊作用域服務
        factory = AsyncMock(side_effect=lambda: Mock())
        container.register_scoped(Mock, factory=factory)

        # 相同作用域返回相同實例
        scope_id = "test-scope"
        result1 = await container.get(Mock, scope_id=scope_id)
        result2 = await container.get(Mock, scope_id=scope_id)
        assert result1 is result2

        # 不同作用域返回不同實例
        result3 = await container.get(Mock, scope_id="other-scope")
        assert result3 is not result1

        # 驗證工廠函數被調用了兩次（兩個作用域）
        assert factory.call_count == 2

    @pytest.mark.asyncio
    async def test_get_transient_service(self):
        """測試獲取瞬時服務"""
        container = DIContainer()

        # 註冊瞬時服務
        factory = AsyncMock(side_effect=lambda: Mock())
        container.register_transient(Mock, factory=factory)

        # 每次獲取都返回新實例
        result1 = await container.get(Mock)
        result2 = await container.get(Mock)

        assert result1 is not result2
        assert factory.call_count == 2

    @pytest.mark.asyncio
    async def test_get_unregistered_service(self):
        """測試獲取未註冊的服務"""
        container = DIContainer()

        with pytest.raises(ValueError) as exc_info:
            await container.get(Mock)

        assert "not registered" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_dependency_injection(self):
        """測試依賴注入功能"""
        container = DIContainer()

        # 簡單的依賴注入測試
        # 使用實例方式註冊服務
        repo_instance = Mock()
        service_instance = Mock()
        service_instance.repo = repo_instance

        container.register_singleton(Mock, instance=repo_instance)
        container.register_singleton(MagicMock, instance=service_instance)

        # 獲取服務
        service = await container.get(MagicMock)
        assert service == service_instance
        assert service.repo == repo_instance

    @pytest.mark.asyncio
    async def test_factory_with_dependencies(self):
        """測試帶依賴的工廠函數"""
        container = DIContainer()

        # 簡單的工廠函數測試
        db_instance = Mock()
        container.register_singleton(Mock, instance=db_instance)

        # 使用實例而非工廠函數
        service_instance = Mock()
        service_instance.db = db_instance
        container.register_singleton(MagicMock, instance=service_instance)

        # 獲取服務
        service = await container.get(MagicMock)
        assert service.db == db_instance

    def test_clear_scope(self):
        """測試清理作用域"""
        container = DIContainer()

        # 設置一些作用域實例
        container._scoped_instances = {
            "scope1": {"service1": Mock()},
            "scope2": {"service2": Mock()},
        }

        # 清理特定作用域
        container.clear_scope("scope1")
        assert "scope1" not in container._scoped_instances
        assert "scope2" in container._scoped_instances

    def test_clear_all_scopes(self):
        """測試清理所有作用域"""
        container = DIContainer()

        # 設置一些作用域實例
        container._scoped_instances = {
            "scope1": {"service1": Mock()},
            "scope2": {"service2": Mock()},
        }

        # 清理所有作用域
        container.clear_all_scopes()
        assert len(container._scoped_instances) == 0

    @pytest.mark.asyncio
    async def test_scope_context_manager(self):
        """測試作用域上下文管理器"""
        container = DIContainer()

        # 註冊作用域服務
        container.register_scoped(Mock, factory=lambda: Mock())

        # 使用上下文管理器
        async with container.scope("test-scope") as scope_id:
            assert scope_id == "test-scope"

            # 在作用域內獲取服務
            service = await container.get(Mock, scope_id=scope_id)
            assert service is not None

            # 確認作用域存在
            assert scope_id in container._scoped_instances

        # 離開上下文後，作用域應被清理
        assert "test-scope" not in container._scoped_instances

    @pytest.mark.asyncio
    async def test_scope_context_manager_auto_id(self):
        """測試自動生成的作用域 ID"""
        container = DIContainer()

        async with container.scope() as scope_id:
            assert scope_id is not None
            assert scope_id.startswith("scope-")

    def test_is_registered(self):
        """測試檢查服務是否已註冊"""
        container = DIContainer()

        # 未註冊的服務
        assert not container.is_registered(Mock)

        # 註冊服務
        container.register_singleton(Mock, instance=Mock())
        assert container.is_registered(Mock)

    def test_get_registered_services(self):
        """測試獲取所有已註冊的服務"""
        container = DIContainer()

        # 註冊多個服務
        class Service1:
            pass

        class Service2:
            pass

        container.register_singleton(Service1, instance=Mock())
        container.register_scoped(Service2, factory=lambda: Mock())

        # 獲取所有服務
        services = container.get_registered_services()
        assert Service1 in services
        assert Service2 in services
        assert len(services) == 2

    @pytest.mark.asyncio
    async def test_concurrent_singleton_creation(self):
        """測試並發創建單例服務"""
        container = DIContainer()

        # 慢速工廠函數，模擬耗時操作
        call_count = 0

        async def slow_factory():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return Mock()

        container.register_singleton(Mock, factory=slow_factory)

        # 並發獲取服務
        results = await asyncio.gather(
            container.get(Mock), container.get(Mock), container.get(Mock)
        )

        # 應該只創建一個實例
        assert call_count == 1
        assert results[0] is results[1]
        assert results[1] is results[2]

    @pytest.mark.asyncio
    async def test_sync_factory_function(self):
        """測試同步工廠函數"""
        container = DIContainer()

        # 同步工廠函數
        def sync_factory():
            return Mock()

        container.register_singleton(Mock, factory=sync_factory)

        # 應該能正常工作
        result = await container.get(Mock)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_instance_error_handling(self):
        """測試創建實例時的錯誤處理"""
        container = DIContainer()

        # 錯誤的工廠函數
        async def error_factory():
            raise Exception("Factory error")

        container.register_singleton(Mock, factory=error_factory)

        # 應該拋出異常
        with pytest.raises(Exception) as exc_info:
            await container.get(Mock)
        assert "Factory error" in str(exc_info.value)

    def test_get_container_function(self):
        """測試獲取全域容器函數"""
        container1 = get_container()
        container2 = get_container()

        # 應該返回相同的實例
        assert container1 is container2
        assert isinstance(container1, DIContainer)

    @pytest.mark.asyncio
    async def test_default_scope_id(self):
        """測試默認作用域 ID"""
        container = DIContainer()

        # 註冊作用域服務
        container.register_scoped(Mock, factory=lambda: Mock())

        # 不提供 scope_id 時使用默認值
        service1 = await container.get(Mock)
        service2 = await container.get(Mock)

        # 應該返回相同實例（都使用 "default" 作用域）
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_unknown_lifetime(self):
        """測試未知的服務生命週期"""
        container = DIContainer()

        # 手動創建錯誤的描述符
        descriptor = ServiceDescriptor(
            service_type=Mock, instance=Mock(), lifetime=ServiceLifetime.SINGLETON
        )
        # 修改為無效的生命週期
        descriptor.lifetime = "invalid"
        container._services[Mock] = descriptor

        # 應該拋出異常
        with pytest.raises(ValueError) as exc_info:
            await container.get(Mock)
        assert "Unknown service lifetime" in str(exc_info.value)

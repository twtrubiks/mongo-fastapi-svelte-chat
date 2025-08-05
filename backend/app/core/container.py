"""依賴注入容器"""
from typing import Any, Callable, Dict, Optional, Type, TypeVar, get_type_hints
from enum import Enum
from contextlib import asynccontextmanager
import asyncio
import inspect
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifetime(Enum):
    """服務生命週期"""
    SINGLETON = "singleton"      # 單例：整個應用程式生命週期中只有一個實例
    SCOPED = "scoped"           # 作用域：每個請求/作用域一個實例
    TRANSIENT = "transient"     # 瞬時：每次請求都創建新實例


class ServiceDescriptor:
    """服務描述符"""
    
    def __init__(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        instance: Optional[T] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON
    ):
        self.service_type = service_type
        self.implementation_type = implementation_type
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime
        
        # 驗證配置
        if sum(bool(x) for x in [implementation_type, factory, instance]) != 1:
            raise ValueError("必須提供 implementation_type、factory 或 instance 中的一個")


class DIContainer:
    """依賴注入容器"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._instances: Dict[Type, Any] = {}
        self._scoped_instances: Dict[str, Dict[Type, Any]] = {}
        self._lock = asyncio.Lock()
    
    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None,
        instance: Optional[T] = None
    ) -> 'DIContainer':
        """
        註冊單例服務
        
        Args:
            service_type: 服務介面類型
            implementation_type: 實現類型
            factory: 工廠函數
            instance: 直接提供的實例
            
        Returns:
            DIContainer: 支援鏈式調用
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON
        )
        self._services[service_type] = descriptor
        logger.debug(f"Registered singleton service: {service_type.__name__}")
        return self
    
    def register_scoped(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'DIContainer':
        """
        註冊作用域服務
        
        Args:
            service_type: 服務介面類型
            implementation_type: 實現類型
            factory: 工廠函數
            
        Returns:
            DIContainer: 支援鏈式調用
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=ServiceLifetime.SCOPED
        )
        self._services[service_type] = descriptor
        logger.debug(f"Registered scoped service: {service_type.__name__}")
        return self
    
    def register_transient(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[..., T]] = None
    ) -> 'DIContainer':
        """
        註冊瞬時服務
        
        Args:
            service_type: 服務介面類型
            implementation_type: 實現類型
            factory: 工廠函數
            
        Returns:
            DIContainer: 支援鏈式調用
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifetime=ServiceLifetime.TRANSIENT
        )
        self._services[service_type] = descriptor
        logger.debug(f"Registered transient service: {service_type.__name__}")
        return self
    
    async def get(self, service_type: Type[T], scope_id: Optional[str] = None) -> T:
        """
        獲取服務實例
        
        Args:
            service_type: 服務類型
            scope_id: 作用域 ID（用於 scoped 服務）
            
        Returns:
            T: 服務實例
            
        Raises:
            ValueError: 服務未註冊
        """
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} not registered")
        
        descriptor = self._services[service_type]
        
        # 處理不同的生命週期
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return await self._get_singleton(descriptor)
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            return await self._get_scoped(descriptor, scope_id)
        elif descriptor.lifetime == ServiceLifetime.TRANSIENT:
            return await self._create_instance(descriptor)
        else:
            raise ValueError(f"Unknown service lifetime: {descriptor.lifetime}")
    
    async def _get_singleton(self, descriptor: ServiceDescriptor) -> Any:
        """獲取單例服務"""
        service_type = descriptor.service_type
        
        # 如果已經有實例，直接返回
        if service_type in self._instances:
            return self._instances[service_type]
        
        # 使用鎖確保線程安全
        async with self._lock:
            # 雙重檢查鎖定
            if service_type in self._instances:
                return self._instances[service_type]
            
            # 創建新實例
            instance = await self._create_instance(descriptor)
            self._instances[service_type] = instance
            logger.debug(f"Created singleton instance: {service_type.__name__}")
            return instance
    
    async def _get_scoped(self, descriptor: ServiceDescriptor, scope_id: Optional[str]) -> Any:
        """獲取作用域服務"""
        if scope_id is None:
            scope_id = "default"
        
        service_type = descriptor.service_type
        
        # 檢查作用域是否存在
        if scope_id not in self._scoped_instances:
            self._scoped_instances[scope_id] = {}
        
        scope_services = self._scoped_instances[scope_id]
        
        # 如果作用域中已有實例，返回
        if service_type in scope_services:
            return scope_services[service_type]
        
        # 創建新實例
        instance = await self._create_instance(descriptor)
        scope_services[service_type] = instance
        logger.debug(f"Created scoped instance: {service_type.__name__} (scope: {scope_id})")
        return instance
    
    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """創建服務實例"""
        # 如果有直接提供的實例
        if descriptor.instance is not None:
            return descriptor.instance
        
        # 如果有工廠函數
        if descriptor.factory is not None:
            return await self._invoke_factory(descriptor.factory)
        
        # 如果有實現類型
        if descriptor.implementation_type is not None:
            return await self._create_from_type(descriptor.implementation_type)
        
        raise ValueError(f"Cannot create instance for {descriptor.service_type.__name__}")
    
    async def _invoke_factory(self, factory: Callable) -> Any:
        """調用工廠函數"""
        try:
            # 檢查工廠函數的參數
            sig = inspect.signature(factory)
            args = []
            
            for param_name, param in sig.parameters.items():
                if param.annotation != inspect.Parameter.empty:
                    # 遞歸解析依賴
                    dependency = await self.get(param.annotation)
                    args.append(dependency)
            
            # 調用工廠函數
            if inspect.iscoroutinefunction(factory):
                return await factory(*args)
            else:
                return factory(*args)
        except Exception as e:
            logger.error(f"Error invoking factory: {e}")
            raise
    
    async def _create_from_type(self, implementation_type: Type) -> Any:
        """從類型創建實例"""
        try:
            # 檢查構造函數的參數
            sig = inspect.signature(implementation_type.__init__)
            args = []
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                if param.annotation != inspect.Parameter.empty:
                    # 遞歸解析依賴
                    dependency = await self.get(param.annotation)
                    args.append(dependency)
            
            # 創建實例
            return implementation_type(*args)
        except Exception as e:
            logger.error(f"Error creating instance of {implementation_type.__name__}: {e}")
            raise
    
    def clear_scope(self, scope_id: str):
        """清理作用域"""
        if scope_id in self._scoped_instances:
            del self._scoped_instances[scope_id]
            logger.debug(f"Cleared scope: {scope_id}")
    
    def clear_all_scopes(self):
        """清理所有作用域"""
        self._scoped_instances.clear()
        logger.debug("Cleared all scopes")
    
    @asynccontextmanager
    async def scope(self, scope_id: str = None):
        """
        作用域上下文管理器
        
        Usage:
            async with container.scope("request-123"):
                service = await container.get(MyService)
        """
        if scope_id is None:
            scope_id = f"scope-{id(self)}"
        
        try:
            yield scope_id
        finally:
            self.clear_scope(scope_id)
    
    def is_registered(self, service_type: Type) -> bool:
        """檢查服務是否已註冊"""
        return service_type in self._services
    
    def get_registered_services(self) -> Dict[Type, ServiceDescriptor]:
        """獲取所有已註冊的服務"""
        return self._services.copy()


# 全域容器實例
container = DIContainer()


def get_container() -> DIContainer:
    """獲取全域容器實例"""
    return container
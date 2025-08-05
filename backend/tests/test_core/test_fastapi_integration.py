"""
測試 FastAPI 依賴注入整合模組
使用 Mock 優先的方式測試所有功能
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import Request, HTTPException
import uuid
from app.core.fastapi_integration import (
    create_dependency_factory,
    get_user_repository,
    get_room_repository,
    get_message_repository,
    get_notification_repository,
    get_user_service,
    get_room_service,
    get_message_service,
    get_notification_service,
    get_invitation_service,
    setup_dependency_injection,
    cleanup_dependency_injection,
    request_scope_middleware,
    get_health_check_info
)


class TestFastAPIIntegration:
    """測試 FastAPI 整合功能"""
    
    @pytest.mark.asyncio
    async def test_create_dependency_factory(self):
        """測試依賴工廠創建"""
        # Mock 容器
        mock_container = AsyncMock()
        mock_service = Mock()
        mock_container.get.return_value = mock_service
        
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        
        # 創建依賴工廠
        with patch('app.core.fastapi_integration.get_container', return_value=mock_container):
            factory = create_dependency_factory(Mock)
            
            # 測試工廠函數
            result = await factory(request=mock_request)
            
            # 驗證
            assert result == mock_service
            assert hasattr(mock_request.state, 'scope_id')
            mock_container.get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_dependency_factory_without_request(self):
        """測試無請求的依賴工廠"""
        # Mock 容器
        mock_container = AsyncMock()
        mock_service = Mock()
        mock_container.get.return_value = mock_service
        
        # 創建依賴工廠
        with patch('app.core.fastapi_integration.get_container', return_value=mock_container):
            factory = create_dependency_factory(Mock)
            
            # 測試工廠函數（無請求）
            result = await factory(request=None)
            
            # 驗證
            assert result == mock_service
            mock_container.get.assert_called_with(Mock, scope_id=None)
    
    @pytest.mark.asyncio
    async def test_dependency_factory_error_handling(self):
        """測試依賴工廠錯誤處理"""
        # Mock 容器拋出異常
        mock_container = AsyncMock()
        mock_container.get.side_effect = Exception("Container error")
        
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        
        # 創建依賴工廠
        with patch('app.core.fastapi_integration.get_container', return_value=mock_container):
            factory = create_dependency_factory(Mock)
            
            # 測試錯誤處理
            with pytest.raises(HTTPException) as exc_info:
                await factory(request=mock_request)
            
            assert exc_info.value.status_code == 500
            assert "Internal server error" in exc_info.value.detail
    
    def test_get_repository_dependencies(self):
        """測試 Repository 依賴獲取函數"""
        # 測試所有 repository 依賴函數
        from fastapi import Depends
        
        # 測試 get_user_repository
        user_repo_dep = get_user_repository()
        assert isinstance(user_repo_dep, type(Depends(lambda: None)))
        
        # 測試 get_room_repository
        room_repo_dep = get_room_repository()
        assert isinstance(room_repo_dep, type(Depends(lambda: None)))
        
        # 測試 get_message_repository
        message_repo_dep = get_message_repository()
        assert isinstance(message_repo_dep, type(Depends(lambda: None)))
        
        # 測試 get_notification_repository
        notification_repo_dep = get_notification_repository()
        assert isinstance(notification_repo_dep, type(Depends(lambda: None)))
    
    def test_get_service_dependencies(self):
        """測試 Service 依賴獲取函數"""
        from fastapi import Depends
        
        # 測試所有 service 依賴函數
        user_service_dep = get_user_service()
        assert isinstance(user_service_dep, type(Depends(lambda: None)))
        
        room_service_dep = get_room_service()
        assert isinstance(room_service_dep, type(Depends(lambda: None)))
        
        message_service_dep = get_message_service()
        assert isinstance(message_service_dep, type(Depends(lambda: None)))
        
        notification_service_dep = get_notification_service()
        assert isinstance(notification_service_dep, type(Depends(lambda: None)))
        
        invitation_service_dep = get_invitation_service()
        assert isinstance(invitation_service_dep, type(Depends(lambda: None)))
    
    @pytest.mark.asyncio
    async def test_setup_dependency_injection(self):
        """測試依賴注入系統設置"""
        # Mock app
        mock_app = Mock()
        mock_app.state = Mock()
        
        # Mock container
        mock_container = Mock()
        
        with patch('app.core.fastapi_integration.get_container', return_value=mock_container):
            with patch('app.core.fastapi_integration.configure_services') as mock_configure:
                # 執行設置
                await setup_dependency_injection(mock_app)
                
                # 驗證
                mock_configure.assert_called_once_with(mock_container)
                assert mock_app.state.di_container == mock_container
    
    @pytest.mark.asyncio
    async def test_setup_dependency_injection_error(self):
        """測試依賴注入設置錯誤處理"""
        # Mock app
        mock_app = Mock()
        mock_app.state = Mock()
        
        # Mock 錯誤
        with patch('app.core.fastapi_integration.get_container', side_effect=Exception("Setup error")):
            # 測試錯誤處理
            with pytest.raises(Exception) as exc_info:
                await setup_dependency_injection(mock_app)
            
            assert str(exc_info.value) == "Setup error"
    
    @pytest.mark.asyncio
    async def test_cleanup_dependency_injection(self):
        """測試依賴注入系統清理"""
        # Mock app with container
        mock_app = Mock()
        mock_container = Mock()
        mock_app.state.di_container = mock_container
        
        # 執行清理
        await cleanup_dependency_injection(mock_app)
        
        # 驗證
        mock_container.clear_all_scopes.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_dependency_injection_no_container(self):
        """測試無容器時的清理"""
        # Mock app without container
        mock_app = Mock()
        mock_app.state = Mock(spec=[])  # 沒有 di_container 屬性
        
        # 執行清理（不應拋出異常）
        await cleanup_dependency_injection(mock_app)
    
    @pytest.mark.asyncio
    async def test_request_scope_middleware(self):
        """測試請求作用域中間件"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.app.state.di_container = Mock()
        
        # Mock call_next
        mock_response = Mock()
        async def mock_call_next(request):
            return mock_response
        
        # 執行中間件
        with patch('uuid.uuid4', return_value='test-scope-id'):
            response = await request_scope_middleware(mock_request, mock_call_next)
        
        # 驗證
        assert response == mock_response
        assert mock_request.state.scope_id == 'test-scope-id'
        mock_request.app.state.di_container.clear_scope.assert_called_with('test-scope-id')
    
    @pytest.mark.asyncio
    async def test_request_scope_middleware_error_handling(self):
        """測試請求作用域中間件錯誤處理"""
        # Mock request
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_container = Mock()
        mock_container.clear_scope.side_effect = Exception("Clear scope error")
        mock_request.app.state.di_container = mock_container
        
        # Mock call_next
        mock_response = Mock()
        async def mock_call_next(request):
            return mock_response
        
        # 執行中間件（清理錯誤不應影響響應）
        response = await request_scope_middleware(mock_request, mock_call_next)
        
        # 驗證
        assert response == mock_response
    
    @pytest.mark.asyncio
    async def test_get_health_check_info_success(self):
        """測試健康檢查資訊獲取成功"""
        # Mock request with container
        mock_request = Mock(spec=Request)
        mock_container = Mock()
        mock_request.app.state.di_container = mock_container
        
        # Mock health check result
        mock_health_info = {
            "status": "healthy",
            "services": {
                "database": "connected",
                "cache": "connected"
            }
        }
        
        with patch('app.core.service_registration.health_check_services', 
                   return_value=mock_health_info) as mock_health_check:
            # 執行健康檢查
            result = await get_health_check_info(mock_request)
            
            # 驗證
            assert result == mock_health_info
            mock_health_check.assert_called_once_with(mock_container)
    
    @pytest.mark.asyncio
    async def test_get_health_check_info_no_container(self):
        """測試無容器時的健康檢查"""
        # Mock request without container
        mock_request = Mock(spec=Request)
        mock_request.app.state = Mock(spec=[])  # 沒有 di_container
        
        # 執行健康檢查
        result = await get_health_check_info(mock_request)
        
        # 驗證
        assert result["status"] == "unhealthy"
        assert "Dependency injection container not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_get_health_check_info_error(self):
        """測試健康檢查錯誤處理"""
        # Mock request with container
        mock_request = Mock(spec=Request)
        mock_container = Mock()
        mock_request.app.state.di_container = mock_container
        
        # Mock health check error
        with patch('app.core.service_registration.health_check_services', 
                   side_effect=Exception("Health check failed")):
            # 執行健康檢查
            result = await get_health_check_info(mock_request)
            
            # 驗證
            assert result["status"] == "unhealthy"
            assert "Health check failed" in result["error"]
    
    def test_dependency_aliases(self):
        """測試依賴注入別名"""
        from app.core.fastapi_integration import (
            UserRepositoryDep,
            RoomRepositoryDep,
            MessageRepositoryDep,
            NotificationRepositoryDep,
            UserServiceDep,
            RoomServiceDep,
            MessageServiceDep,
            NotificationServiceDep,
            InvitationServiceDep
        )
        
        # 驗證所有別名都已正確定義
        assert UserRepositoryDep is not None
        assert RoomRepositoryDep is not None
        assert MessageRepositoryDep is not None
        assert NotificationRepositoryDep is not None
        assert UserServiceDep is not None
        assert RoomServiceDep is not None
        assert MessageServiceDep is not None
        assert NotificationServiceDep is not None
        assert InvitationServiceDep is not None
    
    @pytest.mark.asyncio
    async def test_dependency_factory_with_existing_scope_id(self):
        """測試使用現有 scope_id 的依賴工廠"""
        # Mock 容器
        mock_container = AsyncMock()
        mock_service = Mock()
        mock_container.get.return_value = mock_service
        
        # Mock request with existing scope_id
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.scope_id = "existing-scope-id"
        
        # 創建依賴工廠
        with patch('app.core.fastapi_integration.get_container', return_value=mock_container):
            factory = create_dependency_factory(Mock)
            
            # 測試工廠函數
            result = await factory(request=mock_request)
            
            # 驗證使用現有的 scope_id
            assert result == mock_service
            assert mock_request.state.scope_id == "existing-scope-id"
            mock_container.get.assert_called_with(Mock, scope_id="existing-scope-id")
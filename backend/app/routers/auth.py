"""認證相關的 API 端點（重構版）"""

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import get_current_active_user
from app.core.fastapi_integration import UserServiceDep
from app.models.user import (
    AuthResponse,
    PasswordChange,
    RefreshRequest,
    RefreshResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/auth", tags=["認證"])


@router.post(
    "/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user: UserCreate, service: UserService = UserServiceDep
) -> AuthResponse:
    """
    使用者註冊

    Args:
        user: 使用者註冊資料
        service: 用戶服務實例

    Returns:
        AuthResponse: 新創建的使用者資料和認證token

    Raises:
        HTTPException: 使用者名稱或信箱已存在時拋出 400 錯誤
    """
    # 使用 UserService 創建用戶
    created_user = await service.create_user(user)

    # 創建用戶後自動進行認證並生成 token
    auth_result = await service.authenticate_user(user.username, user.password)

    return AuthResponse(
        access_token=auth_result["access_token"],
        refresh_token=auth_result["refresh_token"],
        token_type=auth_result["token_type"],
        user=created_user,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: UserService = UserServiceDep,
):
    """
    使用者登入

    Args:
        form_data: OAuth2 登入表單資料
        service: 用戶服務實例

    Returns:
        AuthResponse: JWT token 和用戶資料

    Raises:
        HTTPException: 認證失敗時拋出 401 錯誤
    """
    # 使用 UserService 進行認證（authenticate_user 已包含完整 UserResponse）
    auth_result = await service.authenticate_user(
        form_data.username, form_data.password
    )

    return AuthResponse(
        access_token=auth_result["access_token"],
        refresh_token=auth_result["refresh_token"],
        token_type=auth_result["token_type"],
        user=auth_result["user"],
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """
    獲取當前使用者資訊

    Args:
        current_user: 當前登入的使用者

    Returns:
        UserResponse: 使用者資料
    """
    # 確保 _id 映射到 id
    user_data = current_user.copy()
    if "_id" in user_data:
        user_data["id"] = user_data.pop("_id")
    return UserResponse(**user_data)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: RefreshRequest,
    service: UserService = UserServiceDep,
):
    """
    使用 Refresh Token 換發新的 Access Token

    Args:
        request: 包含 refresh_token 的請求
        service: 用戶服務實例

    Returns:
        RefreshResponse: 新的 access_token 和 refresh_token

    Raises:
        HTTPException: Refresh Token 無效或過期時拋出 401 錯誤
    """
    result = await service.refresh_access_token(request.refresh_token)
    return RefreshResponse(**result)


@router.post("/logout")
async def logout():
    """
    使用者登出

    注意：由於 JWT 是無狀態的，這裡只是提供一個端點
    實際的 token 失效需要在客戶端處理
    """
    return {"message": "登出成功"}


@router.put("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(get_current_active_user),
    service: UserService = UserServiceDep,
):
    """修改密碼"""
    user_id = current_user["_id"]
    await service.change_password(
        user_id, password_data.current_password, password_data.new_password
    )
    return {"message": "密碼修改成功"}


@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: dict = Depends(get_current_active_user),
    service: UserService = UserServiceDep,
):
    """
    獲取用戶詳細資料

    Args:
        current_user: 當前登入的使用者
        service: 用戶服務實例

    Returns:
        UserResponse: 使用者詳細資料
    """
    user_id = current_user["_id"]
    return await service.get_user_by_id(user_id)


@router.put("/profile", response_model=UserResponse)
async def update_user_profile(
    user_update: UserUpdate,
    current_user: dict = Depends(get_current_active_user),
    service: UserService = UserServiceDep,
):
    """
    更新用戶資料

    Args:
        user_update: 更新的使用者資料
        current_user: 當前登入的使用者
        service: 用戶服務實例

    Returns:
        UserResponse: 更新後的使用者資料
    """
    user_id = current_user["_id"]
    return await service.update_user(user_id, user_update, user_id)


@router.post("/avatar", response_model=UserResponse)
async def update_user_avatar(
    avatar_url: str,
    current_user: dict = Depends(get_current_active_user),
    service: UserService = UserServiceDep,
):
    """
    更新用戶頭像

    Args:
        avatar_url: 頭像圖片的 URL
        current_user: 當前登入的使用者
        service: 用戶服務實例

    Returns:
        UserResponse: 更新後的使用者資料
    """
    user_id = current_user["_id"]
    update_data = UserUpdate(avatar=avatar_url)
    return await service.update_user(user_id, update_data, user_id)


@router.delete("/profile")
async def delete_user_profile(
    current_user: dict = Depends(get_current_active_user),
    service: UserService = UserServiceDep,
):
    """
    刪除用戶帳號

    Args:
        current_user: 當前登入的使用者
        service: 用戶服務實例

    Returns:
        dict: 刪除結果
    """
    user_id = current_user["_id"]
    await service.delete_user(user_id, user_id)
    return {"message": "帳號刪除成功"}

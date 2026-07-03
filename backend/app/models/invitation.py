"""邀請碼驗證資料模型"""

from pydantic import BaseModel


class InvitationValidateRequest(BaseModel):
    """驗證邀請碼請求"""

    invite_code: str

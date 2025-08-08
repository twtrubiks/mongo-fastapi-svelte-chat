"""系統枚舉類型定義"""

from enum import Enum


class RoomType(str, Enum):
    """房間類型"""

    PUBLIC = "public"  # 公開房間 - 任何人可見可加入
    PRIVATE = "private"  # 私人房間 - 僅邀請加入


class JoinPolicy(str, Enum):
    """加入策略"""

    DIRECT = "direct"  # 直接加入
    INVITE = "invite"  # 邀請鏈接
    PASSWORD = "password"  # 密碼加入


class MemberRole(str, Enum):
    """成員角色"""

    OWNER = "owner"  # 房主 - 完全控制權
    ADMIN = "admin"  # 管理員 - 成員管理權
    MEMBER = "member"  # 成員 - 基本使用權
    GUEST = "guest"  # 訪客 - 只讀權限


class InvitationStatus(str, Enum):
    """邀請狀態"""

    PENDING = "pending"  # 待處理
    ACCEPTED = "accepted"  # 已接受
    REJECTED = "rejected"  # 已拒絕
    EXPIRED = "expired"  # 已過期


class JoinRequestStatus(str, Enum):
    """加入申請狀態"""

    PENDING = "pending"  # 待審核
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 已拒絕
    CANCELLED = "cancelled"  # 已取消

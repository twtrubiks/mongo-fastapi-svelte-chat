"""系統枚舉類型定義"""

from enum import StrEnum


class RoomType(StrEnum):
    """房間類型"""

    PUBLIC = "public"  # 公開房間 - 任何人可見可加入
    PRIVATE = "private"  # 私人房間 - 僅邀請加入


class JoinPolicy(StrEnum):
    """加入策略"""

    DIRECT = "direct"  # 直接加入
    INVITE = "invite"  # 邀請鏈接
    PASSWORD = "password"  # 密碼加入


class MemberRole(StrEnum):
    """成員角色"""

    OWNER = "owner"  # 房主 - 完全控制權
    ADMIN = "admin"  # 管理員 - 成員管理權
    MEMBER = "member"  # 成員 - 基本使用權

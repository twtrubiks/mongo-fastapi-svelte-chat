"""日期時間工具函數"""

from datetime import UTC, datetime


def format_datetime_for_json(v: datetime) -> str:
    """統一的時間格式化函數，確保 UTC 時間以 Z 結尾"""
    if v.tzinfo is None:
        # 如果沒有時區資訊，假設為 UTC
        iso_str = v.replace(tzinfo=UTC).isoformat()
    else:
        iso_str = v.isoformat()

    # 將 +00:00 格式轉換為 Z 格式，確保前端兼容性
    if iso_str.endswith("+00:00"):
        return iso_str.replace("+00:00", "Z")
    return iso_str

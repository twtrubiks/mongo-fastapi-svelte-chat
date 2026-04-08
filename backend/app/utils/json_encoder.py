"""JSON 編碼器工具"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from bson import ObjectId

from app.utils.datetime_utils import format_datetime_for_json


class WebSocketJSONEncoder(json.JSONEncoder):
    """WebSocket 專用的 JSON 編碼器，處理特殊類型的序列化"""

    def default(self, obj: Any) -> Any:
        """
        自定義序列化邏輯

        Args:
            obj: 需要序列化的對象

        Returns:
            序列化後的對象
        """
        if isinstance(obj, datetime):
            return format_datetime_for_json(obj)
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, "__dict__"):
            # 處理自定義對象，轉換為字典
            return obj.__dict__

        # 讓父類處理其他類型
        return super().default(obj)


def safe_json_dumps(data: Any, **kwargs) -> str:
    """
    安全的 JSON 序列化，自動處理特殊類型

    Args:
        data: 需要序列化的數據
        **kwargs: 額外的 json.dumps 參數

    Returns:
        JSON 字符串

    Raises:
        TypeError: 如果無法序列化
    """
    default_kwargs = {
        "ensure_ascii": False,
        "cls": WebSocketJSONEncoder,
        "separators": (",", ":"),  # 緊湊格式
    }
    default_kwargs.update(kwargs)

    try:
        return json.dumps(data, **default_kwargs)
    except TypeError:
        # 如果還是無法序列化，嘗試清理數據
        cleaned_data = clean_data_for_json(data)
        return json.dumps(cleaned_data, **default_kwargs)


def clean_data_for_json(data: Any) -> Any:
    """
    清理數據使其可以進行 JSON 序列化

    Args:
        data: 原始數據

    Returns:
        清理後的數據
    """
    if isinstance(data, dict):
        return {k: clean_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list | tuple):
        return [clean_data_for_json(item) for item in data]
    elif isinstance(data, datetime):
        return format_datetime_for_json(data)
    elif isinstance(data, date):
        return data.isoformat()
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, set):
        return list(data)
    elif hasattr(data, "__dict__"):
        # 處理自定義對象
        return clean_data_for_json(data.__dict__)
    else:
        # 對於其他不可序列化的類型，轉換為字符串
        try:
            json.dumps(data)
            return data
        except TypeError:
            return str(data)

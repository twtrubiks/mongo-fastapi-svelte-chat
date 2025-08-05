"""JSON 編碼器工具"""
import json
from datetime import datetime, date, timezone
from decimal import Decimal
from bson import ObjectId
from typing import Any

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
            # 確保 UTC 時間加上 Z 後綴，統一格式
            if obj.tzinfo is None:
                # 如果沒有時區資訊，假設為 UTC
                return obj.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
            else:
                # 將 +00:00 格式轉換為 Z 格式，確保前端兼容性
                iso_str = obj.isoformat()
                if iso_str.endswith('+00:00'):
                    return iso_str.replace('+00:00', 'Z')
                return iso_str
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif hasattr(obj, '__dict__'):
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
        'ensure_ascii': False,
        'cls': WebSocketJSONEncoder,
        'separators': (',', ':')  # 緊湊格式
    }
    default_kwargs.update(kwargs)
    
    try:
        return json.dumps(data, **default_kwargs)
    except TypeError as e:
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
    elif isinstance(data, (list, tuple)):
        return [clean_data_for_json(item) for item in data]
    elif isinstance(data, datetime):
        # 確保 UTC 時間加上 Z 後綴，統一格式
        if data.tzinfo is None:
            # 如果沒有時區資訊，假設為 UTC
            return data.replace(tzinfo=timezone.utc).isoformat().replace('+00:00', 'Z')
        else:
            # 將 +00:00 格式轉換為 Z 格式，確保前端兼容性
            iso_str = data.isoformat()
            if iso_str.endswith('+00:00'):
                return iso_str.replace('+00:00', 'Z')
            return iso_str
    elif isinstance(data, date):
        return data.isoformat()
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, Decimal):
        return float(data)
    elif isinstance(data, set):
        return list(data)
    elif hasattr(data, '__dict__'):
        # 處理自定義對象
        return clean_data_for_json(data.__dict__)
    else:
        # 對於其他不可序列化的類型，轉換為字符串
        try:
            json.dumps(data)
            return data
        except TypeError:
            return str(data)

def prepare_websocket_message(message_type: str, payload: Any = None, **extra_fields) -> dict:
    """
    準備 WebSocket 訊息格式
    
    Args:
        message_type: 訊息類型
        payload: 訊息載荷
        **extra_fields: 額外字段
        
    Returns:
        格式化的訊息字典
    """
    message = {
        "type": message_type,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    if payload is not None:
        message["payload"] = payload
    
    # 添加額外字段
    message.update(extra_fields)
    
    # 清理數據確保可序列化
    return clean_data_for_json(message)
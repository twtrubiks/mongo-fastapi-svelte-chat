"""測試 JSON 編碼器"""
import json
import pytest
from datetime import datetime, date, timezone, timedelta
from decimal import Decimal
from bson import ObjectId
from app.utils.json_encoder import (
    WebSocketJSONEncoder, 
    safe_json_dumps, 
    clean_data_for_json,
    prepare_websocket_message
)


class TestWebSocketJSONEncoder:
    """測試 WebSocket JSON 編碼器"""
    
    def test_encode_datetime_with_timezone(self):
        """測試帶時區的 datetime 編碼"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = json.dumps(dt, cls=WebSocketJSONEncoder)
        assert result == '"2024-01-01T12:00:00Z"'
    
    def test_encode_datetime_without_timezone(self):
        """測試無時區的 datetime 編碼"""
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = json.dumps(dt, cls=WebSocketJSONEncoder)
        assert result == '"2024-01-01T12:00:00Z"'
    
    def test_encode_datetime_with_offset(self):
        """測試帶偏移的 datetime 編碼"""
        # 創建一個帶 +08:00 時區的時間
        tz = timezone(timedelta(hours=8))
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz)
        result = json.dumps(dt, cls=WebSocketJSONEncoder)
        assert result == '"2024-01-01T12:00:00+08:00"'
    
    def test_encode_date(self):
        """測試 date 編碼"""
        d = date(2024, 1, 1)
        result = json.dumps(d, cls=WebSocketJSONEncoder)
        assert result == '"2024-01-01"'
    
    def test_encode_objectid(self):
        """測試 ObjectId 編碼"""
        oid = ObjectId()
        result = json.dumps(oid, cls=WebSocketJSONEncoder)
        assert result == f'"{str(oid)}"'
    
    def test_encode_decimal(self):
        """測試 Decimal 編碼"""
        d = Decimal("123.45")
        result = json.dumps(d, cls=WebSocketJSONEncoder)
        assert result == "123.45"
    
    def test_encode_custom_object(self):
        """測試自定義對象編碼"""
        class CustomObject:
            def __init__(self):
                self.name = "test"
                self.value = 42
        
        obj = CustomObject()
        result = json.dumps(obj, cls=WebSocketJSONEncoder)
        parsed = json.loads(result)
        assert parsed == {"name": "test", "value": 42}
    
    def test_encode_unsupported_type(self):
        """測試不支持的類型"""
        # 使用一個沒有 __dict__ 的內建類型
        with pytest.raises(TypeError):
            json.dumps(object(), cls=WebSocketJSONEncoder)


class TestSafeJsonDumps:
    """測試安全的 JSON 序列化函數"""
    
    def test_safe_json_dumps_basic(self):
        """測試基本序列化"""
        data = {"name": "測試", "value": 123}
        result = safe_json_dumps(data)
        assert result == '{"name":"測試","value":123}'
    
    def test_safe_json_dumps_with_special_types(self):
        """測試特殊類型序列化"""
        data = {
            "id": ObjectId(),
            "created_at": datetime.now(timezone.utc),
            "price": Decimal("99.99"),
            "date": date.today()
        }
        result = safe_json_dumps(data)
        assert isinstance(result, str)
        # 驗證可以反序列化
        parsed = json.loads(result)
        assert "id" in parsed
        assert "created_at" in parsed
        assert "price" in parsed
        assert "date" in parsed
    
    def test_safe_json_dumps_with_type_error(self):
        """測試處理 TypeError"""
        # 創建一個會導致 TypeError 的對象
        class ProblematicObject:
            def __repr__(self):
                raise Exception("Cannot represent")
        
        data = {"obj": ProblematicObject()}
        result = safe_json_dumps(data)
        assert isinstance(result, str)
    
    def test_safe_json_dumps_custom_kwargs(self):
        """測試自定義參數"""
        data = {"name": "test"}
        result = safe_json_dumps(data, indent=2)
        assert "  " in result  # 應該有縮進


class TestCleanDataForJson:
    """測試數據清理函數"""
    
    def test_clean_dict(self):
        """測試清理字典"""
        data = {
            "id": ObjectId(),
            "time": datetime.now(),
            "nested": {
                "date": date.today(),
                "value": Decimal("100")
            }
        }
        cleaned = clean_data_for_json(data)
        assert isinstance(cleaned["id"], str)
        assert isinstance(cleaned["time"], str)
        assert isinstance(cleaned["nested"]["date"], str)
        assert isinstance(cleaned["nested"]["value"], float)
    
    def test_clean_list(self):
        """測試清理列表"""
        data = [
            ObjectId(),
            datetime.now(),
            date.today(),
            Decimal("50"),
            {"nested": ObjectId()}
        ]
        cleaned = clean_data_for_json(data)
        assert all(isinstance(item, (str, float, dict)) for item in cleaned)
    
    def test_clean_tuple(self):
        """測試清理元組"""
        data = (ObjectId(), datetime.now(), date.today())
        cleaned = clean_data_for_json(data)
        assert isinstance(cleaned, list)
        assert all(isinstance(item, str) for item in cleaned)
    
    def test_clean_set(self):
        """測試清理集合"""
        data = {1, 2, 3}
        cleaned = clean_data_for_json(data)
        assert isinstance(cleaned, list)
        assert set(cleaned) == {1, 2, 3}
    
    def test_clean_custom_object(self):
        """測試清理自定義對象"""
        class CustomObject:
            def __init__(self):
                self.id = ObjectId()
                self.created = datetime.now()
        
        obj = CustomObject()
        cleaned = clean_data_for_json(obj)
        assert isinstance(cleaned["id"], str)
        assert isinstance(cleaned["created"], str)
    
    def test_clean_unserializable(self):
        """測試清理不可序列化的對象"""
        # 使用一個無法序列化的對象
        data = {"func": lambda x: x}
        cleaned = clean_data_for_json(data)
        # lambda 會被轉換為它的 __dict__，是個空字典
        assert isinstance(cleaned["func"], dict)
    
    def test_clean_datetime_with_timezone(self):
        """測試清理帶時區的 datetime"""
        dt_utc = datetime.now(timezone.utc)
        cleaned = clean_data_for_json(dt_utc)
        assert cleaned.endswith("Z")
        
        # 測試 +00:00 格式
        dt = datetime.now(timezone.utc)
        iso_str = dt.isoformat()
        if iso_str.endswith("+00:00"):
            cleaned = clean_data_for_json(dt)
            assert cleaned.endswith("Z")


class TestPrepareWebsocketMessage:
    """測試 WebSocket 訊息準備函數"""
    
    def test_basic_message(self):
        """測試基本訊息"""
        msg = prepare_websocket_message("test")
        assert msg["type"] == "test"
        assert "timestamp" in msg
        assert "payload" not in msg
    
    def test_message_with_payload(self):
        """測試帶載荷的訊息"""
        payload = {"data": "test"}
        msg = prepare_websocket_message("test", payload)
        assert msg["type"] == "test"
        assert msg["payload"] == payload
        assert "timestamp" in msg
    
    def test_message_with_extra_fields(self):
        """測試帶額外字段的訊息"""
        msg = prepare_websocket_message(
            "test",
            {"data": "test"},
            user_id="123",
            room_id="456"
        )
        assert msg["type"] == "test"
        assert msg["user_id"] == "123"
        assert msg["room_id"] == "456"
    
    def test_message_with_special_types(self):
        """測試帶特殊類型的訊息"""
        payload = {
            "id": ObjectId(),
            "created": datetime.now(),
            "price": Decimal("99.99")
        }
        msg = prepare_websocket_message("test", payload)
        # 確保訊息可以被序列化
        json_str = json.dumps(msg)
        assert isinstance(json_str, str)
    
    def test_message_timestamp_format(self):
        """測試時間戳格式"""
        msg = prepare_websocket_message("test")
        # 時間戳應該是 ISO 格式的字符串
        assert isinstance(msg["timestamp"], str)
        # 應該可以解析回 datetime
        dt = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
        assert isinstance(dt, datetime)
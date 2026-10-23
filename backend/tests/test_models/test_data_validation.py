"""app.models 的輸入驗證邊界、列舉契約與時間序列化測試"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.enums import JoinPolicy, MemberRole, RoomType
from app.models.message import (
    MAX_CONTENT_LENGTH,
    MessageCreate,
    MessageResponse,
    MessageSearchQuery,
    MessageStatus,
    MessageType,
    MessageUpdate,
)
from app.models.notification import NotificationStatus, NotificationType
from app.models.room import RoomBase, RoomCreate, RoomInDB, RoomSummary, RoomUpdate
from app.models.user import PasswordChange, UserCreate, UserResponse

ROOM_ID = "507f1f77bcf86cd799439011"
NAIVE_TIME = datetime(2026, 1, 2, 3, 4, 5)


def _accepts(model, **fields) -> bool:
    try:
        model(**fields)
        return True
    except ValidationError:
        return False


@pytest.mark.unit
class TestRoomValidation:
    """房間建立 / 更新的欄位邊界"""

    @pytest.mark.parametrize("model", [RoomCreate, RoomUpdate])
    @pytest.mark.parametrize(
        ("name", "ok"),
        [("", False), ("a", True), ("a" * 100, True), ("a" * 101, False)],
    )
    def test_name_length(self, model, name, ok):
        assert _accepts(model, name=name) is ok

    @pytest.mark.parametrize("model", [RoomCreate, RoomUpdate])
    @pytest.mark.parametrize(("length", "ok"), [(500, True), (501, False)])
    def test_description_length(self, model, length, ok):
        assert _accepts(model, name="room", description="d" * length) is ok

    @pytest.mark.parametrize("model", [RoomCreate, RoomUpdate])
    @pytest.mark.parametrize(
        ("max_members", "ok"), [(1, False), (2, True), (1000, True), (1001, False)]
    )
    def test_max_members_range(self, model, max_members, ok):
        assert _accepts(model, name="room", max_members=max_members) is ok

    @pytest.mark.parametrize("model", [RoomCreate, RoomUpdate])
    @pytest.mark.parametrize(
        ("password", "ok"),
        [
            ("", False),
            ("12345", False),
            ("123456", True),
            ("p" * 128, True),
            ("p" * 129, False),
        ],
    )
    def test_password_length(self, model, password, ok):
        assert _accepts(model, name="room", password=password) is ok

    @pytest.mark.parametrize("field", ["name", "description", "max_members"])
    def test_update_constraints_match_stored_model(self, field):
        """RoomUpdate 的限制必須與 RoomInDB（繼承 RoomBase）一致，
        否則可寫入讀不回來的資料，含該房間的列表會整頁 500"""
        assert (
            RoomUpdate.model_fields[field].metadata
            == RoomBase.model_fields[field].metadata
        )
        assert issubclass(RoomInDB, RoomBase)

    def test_password_constraints_match_between_create_and_update(self):
        assert (
            RoomUpdate.model_fields["password"].metadata
            == RoomCreate.model_fields["password"].metadata
        )

    def test_defaults(self):
        room = RoomCreate(name="room")
        assert room.room_type == RoomType.PUBLIC
        assert room.join_policy == JoinPolicy.DIRECT
        assert room.max_members == 100


@pytest.mark.unit
class TestUserValidation:
    """使用者註冊 / 改密碼的欄位邊界"""

    @pytest.mark.parametrize(
        ("username", "ok"),
        [("ab", False), ("abc", True), ("a" * 50, True), ("a" * 51, False)],
    )
    def test_username_length(self, username, ok):
        assert (
            _accepts(
                UserCreate, username=username, email="u@example.com", password="123456"
            )
            is ok
        )

    @pytest.mark.parametrize(("password", "ok"), [("12345", False), ("123456", True)])
    def test_register_password_min_length(self, password, ok):
        assert (
            _accepts(
                UserCreate, username="user", email="u@example.com", password=password
            )
            is ok
        )

    def test_email_format(self):
        assert not _accepts(
            UserCreate, username="user", email="not-an-email", password="123456"
        )

    @pytest.mark.parametrize(("password", "ok"), [("12345", False), ("123456", True)])
    def test_password_change_new_password_min_length(self, password, ok):
        assert (
            _accepts(PasswordChange, current_password="old", new_password=password)
            is ok
        )

    def test_password_change_requires_current_password(self):
        assert not _accepts(PasswordChange, current_password="", new_password="123456")


@pytest.mark.unit
class TestMessageValidation:
    """訊息內容與搜尋參數的邊界"""

    @pytest.mark.parametrize(
        ("length", "ok"),
        [
            (0, False),
            (1, True),
            (MAX_CONTENT_LENGTH, True),
            (MAX_CONTENT_LENGTH + 1, False),
        ],
    )
    def test_create_content_length(self, length, ok):
        assert _accepts(MessageCreate, room_id=ROOM_ID, content="x" * length) is ok

    @pytest.mark.parametrize(
        ("length", "ok"),
        [
            (0, False),
            (1, True),
            (MAX_CONTENT_LENGTH, True),
            (MAX_CONTENT_LENGTH + 1, False),
        ],
    )
    def test_update_content_length(self, length, ok):
        assert _accepts(MessageUpdate, content="x" * length) is ok

    def test_content_limit_is_2000(self):
        assert MAX_CONTENT_LENGTH == 2000

    @pytest.mark.parametrize(("length", "ok"), [(64, True), (65, False)])
    def test_client_id_length(self, length, ok):
        assert (
            _accepts(
                MessageCreate, room_id=ROOM_ID, content="hi", client_id="c" * length
            )
            is ok
        )

    def test_create_defaults(self):
        message = MessageCreate(room_id=ROOM_ID, content="hi")
        assert message.message_type == MessageType.TEXT
        assert message.client_id is None

    @pytest.mark.parametrize(
        ("fields", "ok"),
        [
            ({"page": 1}, True),
            ({"page": 0}, False),
            ({"page_size": 1}, True),
            ({"page_size": 100}, True),
            ({"page_size": 0}, False),
            ({"page_size": 101}, False),
            ({"keyword": "a"}, True),
            ({"keyword": ""}, False),
            ({"keyword": "k" * 100}, True),
            ({"keyword": "k" * 101}, False),
        ],
    )
    def test_search_query_bounds(self, fields, ok):
        assert _accepts(MessageSearchQuery, **fields) is ok

    def test_search_query_defaults(self):
        query = MessageSearchQuery()
        assert (query.page, query.page_size) == (1, 20)


@pytest.mark.unit
class TestEnumWireValues:
    """列舉的字串值是前後端與既有資料的契約（frontend/src/lib/types.ts）"""

    @pytest.mark.parametrize(
        ("enum", "expected"),
        [
            (RoomType, {"PUBLIC": "public", "PRIVATE": "private"}),
            (
                JoinPolicy,
                {"DIRECT": "direct", "INVITE": "invite", "PASSWORD": "password"},
            ),
            (MemberRole, {"OWNER": "owner", "ADMIN": "admin", "MEMBER": "member"}),
            (
                MessageType,
                {"TEXT": "text", "IMAGE": "image", "FILE": "file", "SYSTEM": "system"},
            ),
            (MessageStatus, {"SENT": "sent", "DELETED": "deleted"}),
            (NotificationType, {"MESSAGE": "message", "SYSTEM": "system"}),
            (NotificationStatus, {"UNREAD": "unread", "READ": "read"}),
        ],
    )
    def test_values(self, enum, expected):
        assert {member.name: member.value for member in enum} == expected

    def test_json_payload_with_string_values(self):
        """前端送出的是字串值"""
        room = RoomCreate.model_validate_json(
            '{"name": "r", "room_type": "private", "join_policy": "password"}'
        )
        assert room.room_type is RoomType.PRIVATE
        assert room.join_policy is JoinPolicy.PASSWORD


@pytest.mark.unit
class TestDatetimeSerialization:
    """MongoDB 讀出的 naive datetime 序列化時必須補上 UTC 時區"""

    def test_room_summary(self):
        summary = RoomSummary(
            id=ROOM_ID,
            name="r",
            owner_id="u",
            created_at=NAIVE_TIME,
            updated_at=NAIVE_TIME,
        )
        dumped = summary.model_dump()
        assert dumped["created_at"] == "2026-01-02T03:04:05+00:00"
        assert dumped["updated_at"] == "2026-01-02T03:04:05+00:00"

    def test_user_response(self):
        user = UserResponse(
            id="u",
            username="user",
            email="u@example.com",
            created_at=NAIVE_TIME,
            updated_at=NAIVE_TIME,
        )
        assert user.model_dump()["created_at"] == "2026-01-02T03:04:05+00:00"

    def test_message_response(self):
        message = MessageResponse(
            id="m",
            room_id=ROOM_ID,
            user_id="u",
            username="user",
            content="hi",
            message_type=MessageType.TEXT,
            status=MessageStatus.SENT,
            edited=True,
            edited_at=NAIVE_TIME,
            created_at=NAIVE_TIME,
            updated_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        )
        dumped = message.model_dump()
        assert dumped["created_at"] == "2026-01-02T03:04:05Z"
        assert dumped["updated_at"] == "2026-01-02T03:04:05Z"
        assert dumped["edited_at"] == "2026-01-02T03:04:05Z"

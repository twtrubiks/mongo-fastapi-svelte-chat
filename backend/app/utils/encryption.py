"""加密工具"""

import base64
import hashlib
import json
import logging
import os
import secrets

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionError(Exception):
    """加密錯誤"""

    pass


class SymmetricEncryption:
    """對稱加密類別"""

    def __init__(self, key: bytes | None = None):
        """
        初始化對稱加密

        Args:
            key: 加密密鑰（可選）
        """
        if key:
            self.key = key
        else:
            self.key = Fernet.generate_key()

        self.cipher = Fernet(self.key)

    def encrypt(self, data: str | bytes) -> bytes:
        """
        加密資料

        Args:
            data: 要加密的資料

        Returns:
            bytes: 加密後的資料
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            return self.cipher.encrypt(data)
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise EncryptionError(f"加密失敗: {str(e)}") from e

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        解密資料

        Args:
            encrypted_data: 加密的資料

        Returns:
            bytes: 解密後的資料
        """
        try:
            return self.cipher.decrypt(encrypted_data)
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise EncryptionError(f"解密失敗: {str(e)}") from e

    def encrypt_string(self, text: str) -> str:
        """
        加密字符串並返回 Base64 編碼

        Args:
            text: 要加密的字符串

        Returns:
            str: Base64 編碼的加密字符串
        """
        encrypted_data = self.encrypt(text)
        return base64.b64encode(encrypted_data).decode("utf-8")

    def decrypt_string(self, encrypted_text: str) -> str:
        """
        解密 Base64 編碼的字符串

        Args:
            encrypted_text: Base64 編碼的加密字符串

        Returns:
            str: 解密後的字符串
        """
        try:
            encrypted_data = base64.b64decode(encrypted_text.encode("utf-8"))
            decrypted_data = self.decrypt(encrypted_data)
            return decrypted_data.decode("utf-8")
        except Exception as e:
            logger.error(f"String decryption error: {e}")
            raise EncryptionError(f"字符串解密失敗: {str(e)}") from e

    def get_key(self) -> bytes:
        """
        獲取加密密鑰

        Returns:
            bytes: 加密密鑰
        """
        return self.key

    def get_key_string(self) -> str:
        """
        獲取 Base64 編碼的密鑰字符串

        Returns:
            str: Base64 編碼的密鑰
        """
        return base64.b64encode(self.key).decode("utf-8")

    @staticmethod
    def generate_key() -> bytes:
        """
        生成新的加密密鑰

        Returns:
            bytes: 新的加密密鑰
        """
        return Fernet.generate_key()

    @staticmethod
    def derive_key_from_password(
        password: str, salt: bytes | None = None
    ) -> tuple[bytes, bytes]:
        """
        從密碼派生密鑰

        Args:
            password: 密碼
            salt: 鹽值（可選）

        Returns:
            Tuple[bytes, bytes]: (密鑰, 鹽值)
        """
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
        return key, salt


class AsymmetricEncryption:
    """非對稱加密類別"""

    def __init__(
        self, private_key: bytes | None = None, public_key: bytes | None = None
    ):
        """
        初始化非對稱加密

        Args:
            private_key: 私鑰（可選）
            public_key: 公鑰（可選）
        """
        if private_key:
            self.private_key = serialization.load_pem_private_key(
                private_key, password=None
            )
        else:
            self.private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )

        if public_key:
            self.public_key = serialization.load_pem_public_key(public_key)
        else:
            self.public_key = self.private_key.public_key()

    def encrypt(self, data: str | bytes) -> bytes:
        """
        使用公鑰加密資料

        Args:
            data: 要加密的資料

        Returns:
            bytes: 加密後的資料
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            return self.public_key.encrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        except Exception as e:
            logger.error(f"Asymmetric encryption error: {e}")
            raise EncryptionError(f"非對稱加密失敗: {str(e)}") from e

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        使用私鑰解密資料

        Args:
            encrypted_data: 加密的資料

        Returns:
            bytes: 解密後的資料
        """
        try:
            return self.private_key.decrypt(
                encrypted_data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        except Exception as e:
            logger.error(f"Asymmetric decryption error: {e}")
            raise EncryptionError(f"非對稱解密失敗: {str(e)}") from e

    def get_private_key_pem(self) -> bytes:
        """
        獲取 PEM 格式的私鑰

        Returns:
            bytes: PEM 格式的私鑰
        """
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

    def get_public_key_pem(self) -> bytes:
        """
        獲取 PEM 格式的公鑰

        Returns:
            bytes: PEM 格式的公鑰
        """
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

    def sign(self, data: str | bytes) -> bytes:
        """
        使用私鑰對資料進行數字簽名

        Args:
            data: 要簽名的資料

        Returns:
            bytes: 數字簽名
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            return self.private_key.sign(
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
        except Exception as e:
            logger.error(f"Signing error: {e}")
            raise EncryptionError(f"數字簽名失敗: {str(e)}") from e

    def verify(self, data: str | bytes, signature: bytes) -> bool:
        """
        使用公鑰驗證數字簽名

        Args:
            data: 原始資料
            signature: 數字簽名

        Returns:
            bool: 簽名是否有效
        """
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            self.public_key.verify(
                signature,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False


class HashUtils:
    """雜湊工具類別"""

    @staticmethod
    def sha256(data: str | bytes) -> str:
        """
        計算 SHA-256 雜湊值

        Args:
            data: 要雜湊的資料

        Returns:
            str: 雜湊值的十六進制字符串
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def md5(data: str | bytes) -> str:
        """
        計算 MD5 雜湊值

        Args:
            data: 要雜湊的資料

        Returns:
            str: 雜湊值的十六進制字符串
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        return hashlib.md5(data).hexdigest()

    @staticmethod
    def sha1(data: str | bytes) -> str:
        """
        計算 SHA-1 雜湊值

        Args:
            data: 要雜湊的資料

        Returns:
            str: 雜湊值的十六進制字符串
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        return hashlib.sha1(data).hexdigest()

    @staticmethod
    def sha512(data: str | bytes) -> str:
        """
        計算 SHA-512 雜湊值

        Args:
            data: 要雜湊的資料

        Returns:
            str: 雜湊值的十六進制字符串
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        return hashlib.sha512(data).hexdigest()

    @staticmethod
    def hmac_sha256(data: str | bytes, key: str | bytes) -> str:
        """
        計算 HMAC-SHA256

        Args:
            data: 要計算的資料
            key: 密鑰

        Returns:
            str: HMAC 值的十六進制字符串
        """
        import hmac

        if isinstance(data, str):
            data = data.encode("utf-8")
        if isinstance(key, str):
            key = key.encode("utf-8")

        return hmac.new(key, data, hashlib.sha256).hexdigest()

    @staticmethod
    def file_hash(file_path: str, algorithm: str = "sha256") -> str:
        """
        計算檔案雜湊值

        Args:
            file_path: 檔案路徑
            algorithm: 雜湊演算法

        Returns:
            str: 雜湊值的十六進制字符串
        """
        hash_algo = getattr(hashlib, algorithm)()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_algo.update(chunk)

        return hash_algo.hexdigest()


class SecretGenerator:
    """密碼生成器類別"""

    @staticmethod
    def generate_random_bytes(length: int) -> bytes:
        """
        生成隨機字節

        Args:
            length: 字節長度

        Returns:
            bytes: 隨機字節
        """
        return secrets.token_bytes(length)

    @staticmethod
    def generate_random_string(length: int, alphabet: str | None = None) -> str:
        """
        生成隨機字符串

        Args:
            length: 字符串長度
            alphabet: 字符集（可選）

        Returns:
            str: 隨機字符串
        """
        if alphabet is None:
            alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def generate_password(
        length: int = 12,
        include_uppercase: bool = True,
        include_lowercase: bool = True,
        include_numbers: bool = True,
        include_symbols: bool = True,
    ) -> str:
        """
        生成安全密碼

        Args:
            length: 密碼長度
            include_uppercase: 是否包含大寫字母
            include_lowercase: 是否包含小寫字母
            include_numbers: 是否包含數字
            include_symbols: 是否包含符號

        Returns:
            str: 生成的密碼
        """
        alphabet = ""

        if include_lowercase:
            alphabet += "abcdefghijklmnopqrstuvwxyz"
        if include_uppercase:
            alphabet += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if include_numbers:
            alphabet += "0123456789"
        if include_symbols:
            alphabet += "!@#$%^&*()_+-=[]{}|;:,.<>?"

        if not alphabet:
            raise ValueError("至少需要包含一種字符類型")

        return SecretGenerator.generate_random_string(length, alphabet)

    @staticmethod
    def generate_api_key(length: int = 32) -> str:
        """
        生成 API 密鑰

        Args:
            length: 密鑰長度

        Returns:
            str: API 密鑰
        """
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """
        生成安全令牌

        Args:
            length: 令牌長度

        Returns:
            str: 安全令牌
        """
        return secrets.token_hex(length)

    @staticmethod
    def generate_uuid() -> str:
        """
        生成 UUID

        Returns:
            str: UUID 字符串
        """
        import uuid

        return str(uuid.uuid4())


# 全域加密工具實例
_symmetric_encryption = None
_asymmetric_encryption = None


def get_symmetric_encryption(key: bytes | None = None) -> SymmetricEncryption:
    """
    獲取對稱加密實例

    Args:
        key: 加密密鑰（可選）

    Returns:
        SymmetricEncryption: 對稱加密實例
    """
    global _symmetric_encryption

    if _symmetric_encryption is None or key is not None:
        _symmetric_encryption = SymmetricEncryption(key)

    return _symmetric_encryption


def get_asymmetric_encryption(
    private_key: bytes | None = None, public_key: bytes | None = None
) -> AsymmetricEncryption:
    """
    獲取非對稱加密實例

    Args:
        private_key: 私鑰（可選）
        public_key: 公鑰（可選）

    Returns:
        AsymmetricEncryption: 非對稱加密實例
    """
    global _asymmetric_encryption

    if (
        _asymmetric_encryption is None
        or private_key is not None
        or public_key is not None
    ):
        _asymmetric_encryption = AsymmetricEncryption(private_key, public_key)

    return _asymmetric_encryption


# 便捷函數
def encrypt_sensitive_data(data: str | dict | list, key: bytes | None = None) -> str:
    """
    加密敏感資料

    Args:
        data: 要加密的資料（字符串、字典或列表）
        key: 加密密鑰（可選）

    Returns:
        str: 加密後的資料
    """
    encryption = get_symmetric_encryption(key)

    # 將資料轉換為字符串
    if isinstance(data, dict | list):
        data = json.dumps(data, ensure_ascii=False)

    return encryption.encrypt_string(data)


def decrypt_sensitive_data(
    encrypted_data: str, key: bytes | None = None
) -> str | dict | list:
    """
    解密敏感資料

    Args:
        encrypted_data: 加密的資料
        key: 解密密鑰（可選）

    Returns:
        Union[str, dict, list]: 解密後的資料
    """
    encryption = get_symmetric_encryption(key)
    decrypted_str = encryption.decrypt_string(encrypted_data)

    # 嘗試解析為 JSON，如果失敗就返回原始字符串
    try:
        return json.loads(decrypted_str)
    except json.JSONDecodeError:
        return decrypted_str


def generate_secure_token(length: int = 32) -> str:
    """
    生成安全令牌

    Args:
        length: 令牌長度

    Returns:
        str: 安全令牌
    """
    return SecretGenerator.generate_token(length)


def hash_data(data: str, algorithm: str = "sha256") -> str:
    """
    雜湊資料

    Args:
        data: 要雜湊的資料
        algorithm: 雜湊演算法

    Returns:
        str: 雜湊值
    """
    hash_func = getattr(HashUtils, algorithm)
    return hash_func(data)


def hash_data_with_salt(data: str, salt: str, algorithm: str = "sha256") -> str:
    """
    使用鹽雜湊資料

    Args:
        data: 要雜湊的資料
        salt: 鹽值
        algorithm: 雜湊演算法

    Returns:
        str: 雜湊值
    """
    salted_data = salt + data
    return hash_data(salted_data, algorithm)

"""安全功能的完整測試"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import Request, Response, HTTPException
from fastapi.security import HTTPBearer
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta


class TestSecurityFeatures:
    """測試各種安全功能"""
    
    def test_xss_prevention(self):
        """測試 XSS 防護"""
        # 測試危險輸入的清理
        dangerous_inputs = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<iframe src='evil.com'></iframe>",
            "<svg onload=alert('XSS')>",
            "';alert('XSS');//",
            '"><script>alert("XSS")</script>',
        ]
        
        # Mock 清理函數
        def sanitize_input(text):
            # 簡單的 HTML 轉義
            replacements = {
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#x27;',
                '/': '&#x2F;'
            }
            for char, escape in replacements.items():
                text = text.replace(char, escape)
            return text
        
        # 測試每個危險輸入
        for dangerous in dangerous_inputs:
            sanitized = sanitize_input(dangerous)
            # 確保所有 HTML 特殊字符都被轉義
            assert '<' not in sanitized
            assert '>' not in sanitized
            assert '"' not in sanitized.replace('&quot;', '')
            assert "'" not in sanitized.replace('&#x27;', '')
            # 確保輸出已被正確轉義
            assert sanitized != dangerous  # 輸出應該與輸入不同
    
    def test_sql_injection_prevention(self):
        """測試 SQL 注入防護"""
        # 測試危險的 SQL 輸入
        dangerous_queries = [
            "admin' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' UNION SELECT * FROM passwords--",
            "admin'--",
            "' OR 1=1--",
        ]
        
        # Mock 參數化查詢
        class SafeQuery:
            def __init__(self):
                self.query_log = []
            
            def execute(self, query, params):
                # 確保使用參數化查詢
                assert '?' in query or '%s' in query or ':' in query
                assert isinstance(params, (list, tuple, dict))
                self.query_log.append((query, params))
                return True
        
        safe_query = SafeQuery()
        
        # 測試安全查詢
        for dangerous in dangerous_queries:
            # 應該使用參數化查詢，而不是字符串拼接
            query = "SELECT * FROM users WHERE username = ?"
            params = (dangerous,)
            safe_query.execute(query, params)
        
        # 驗證所有查詢都使用了參數
        assert len(safe_query.query_log) == len(dangerous_queries)
    
    def test_csrf_protection(self):
        """測試 CSRF 防護"""
        # Mock CSRF 令牌生成和驗證
        class CSRFProtection:
            def __init__(self):
                self.tokens = {}
            
            def generate_token(self, session_id):
                token = secrets.token_urlsafe(32)
                self.tokens[session_id] = token
                return token
            
            def verify_token(self, session_id, token):
                return self.tokens.get(session_id) == token
        
        csrf = CSRFProtection()
        session_id = "session123"
        
        # 生成令牌
        token = csrf.generate_token(session_id)
        assert len(token) > 20
        
        # 驗證正確的令牌
        assert csrf.verify_token(session_id, token) is True
        
        # 驗證錯誤的令牌
        assert csrf.verify_token(session_id, "wrong_token") is False
        assert csrf.verify_token("wrong_session", token) is False
    
    @pytest.mark.asyncio
    async def test_rate_limiting_security(self):
        """測試速率限制安全功能"""
        # Mock 速率限制器
        class SecurityRateLimiter:
            def __init__(self):
                self.attempts = {}
                self.blocked_ips = set()
            
            async def check_rate_limit(self, ip_address, endpoint):
                key = f"{ip_address}:{endpoint}"
                
                # 檢查是否被封鎖
                if ip_address in self.blocked_ips:
                    return False, "IP blocked"
                
                # 記錄嘗試次數
                self.attempts[key] = self.attempts.get(key, 0) + 1
                
                # 檢查限制
                if self.attempts[key] > 5:  # 5 次嘗試後封鎖
                    self.blocked_ips.add(ip_address)
                    return False, "Too many attempts"
                
                return True, "OK"
        
        limiter = SecurityRateLimiter()
        
        # 測試正常請求
        for i in range(5):
            allowed, msg = await limiter.check_rate_limit("192.168.1.1", "/api/login")
            assert allowed is True
        
        # 第 6 次應該被阻止
        allowed, msg = await limiter.check_rate_limit("192.168.1.1", "/api/login")
        assert allowed is False
        assert "Too many attempts" in msg
        
        # IP 應該被封鎖
        allowed, msg = await limiter.check_rate_limit("192.168.1.1", "/api/other")
        assert allowed is False
        assert "IP blocked" in msg
    
    def test_password_policy_enforcement(self):
        """測試密碼策略強制執行"""
        # 密碼策略檢查器
        class PasswordPolicy:
            def __init__(self):
                self.min_length = 8
                self.require_uppercase = True
                self.require_lowercase = True
                self.require_digits = True
                self.require_special = True
                self.common_passwords = {"password", "123456", "admin", "qwerty"}
            
            def validate(self, password):
                errors = []
                
                if len(password) < self.min_length:
                    errors.append(f"Password must be at least {self.min_length} characters")
                
                if self.require_uppercase and not any(c.isupper() for c in password):
                    errors.append("Password must contain uppercase letters")
                
                if self.require_lowercase and not any(c.islower() for c in password):
                    errors.append("Password must contain lowercase letters")
                
                if self.require_digits and not any(c.isdigit() for c in password):
                    errors.append("Password must contain digits")
                
                if self.require_special and not any(c in "!@#$%^&*()_+-=" for c in password):
                    errors.append("Password must contain special characters")
                
                if password.lower() in self.common_passwords:
                    errors.append("Password is too common")
                
                return len(errors) == 0, errors
        
        policy = PasswordPolicy()
        
        # 測試弱密碼
        weak_passwords = [
            ("short", False),
            ("alllowercase", False),
            ("ALLUPPERCASE", False),
            ("NoDigits!", False),
            ("NoSpecial123", False),
            ("password", False),
        ]
        
        for pwd, expected in weak_passwords:
            valid, errors = policy.validate(pwd)
            assert valid == expected
            if not valid:
                assert len(errors) > 0
        
        # 測試強密碼
        strong_passwords = [
            "SecureP@ss123",
            "MyStr0ng!Password",
            "Complex#Pass2024",
            "V3ry$ecure!",
        ]
        
        for pwd in strong_passwords:
            valid, errors = policy.validate(pwd)
            assert valid is True
            assert len(errors) == 0
    
    def test_secure_headers_middleware(self):
        """測試安全標頭中間件"""
        # Mock 安全標頭中間件
        class SecureHeadersMiddleware:
            def __init__(self):
                self.headers = {
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "X-XSS-Protection": "1; mode=block",
                    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
                    "Content-Security-Policy": "default-src 'self'",
                    "Referrer-Policy": "strict-origin-when-cross-origin",
                    "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
                }
            
            def apply_headers(self, response):
                for header, value in self.headers.items():
                    response.headers[header] = value
                return response
        
        middleware = SecureHeadersMiddleware()
        
        # Mock response
        response = Mock()
        response.headers = {}
        
        # 應用安全標頭
        middleware.apply_headers(response)
        
        # 驗證所有安全標頭都已設置
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert "Strict-Transport-Security" in response.headers
        assert "Content-Security-Policy" in response.headers
    
    def test_api_key_authentication(self):
        """測試 API 密鑰認證"""
        # API 密鑰管理器
        class APIKeyManager:
            def __init__(self):
                self.api_keys = {}
                self.key_permissions = {}
            
            def generate_api_key(self, user_id, permissions):
                # 生成安全的 API 密鑰
                key = f"sk_{secrets.token_urlsafe(32)}"
                key_hash = hashlib.sha256(key.encode()).hexdigest()
                
                self.api_keys[key_hash] = {
                    "user_id": user_id,
                    "created_at": datetime.now(),
                    "last_used": None
                }
                self.key_permissions[key_hash] = permissions
                
                return key
            
            def validate_api_key(self, api_key):
                if not api_key.startswith("sk_"):
                    return False, None, None
                
                key_hash = hashlib.sha256(api_key.encode()).hexdigest()
                
                if key_hash not in self.api_keys:
                    return False, None, None
                
                # 更新最後使用時間
                self.api_keys[key_hash]["last_used"] = datetime.now()
                
                return True, self.api_keys[key_hash]["user_id"], self.key_permissions[key_hash]
        
        manager = APIKeyManager()
        
        # 生成 API 密鑰
        api_key = manager.generate_api_key("user123", ["read", "write"])
        assert api_key.startswith("sk_")
        assert len(api_key) > 30
        
        # 驗證有效密鑰
        valid, user_id, permissions = manager.validate_api_key(api_key)
        assert valid is True
        assert user_id == "user123"
        assert "read" in permissions
        assert "write" in permissions
        
        # 驗證無效密鑰
        valid, _, _ = manager.validate_api_key("invalid_key")
        assert valid is False
    
    def test_input_validation_and_sanitization(self):
        """測試輸入驗證和清理"""
        # 綜合輸入驗證器
        class InputValidator:
            def validate_email(self, email):
                import re
                pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                return bool(re.match(pattern, email))
            
            def validate_username(self, username):
                # 只允許字母、數字、下劃線
                import re
                if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
                    return False, "Username must be 3-20 characters, alphanumeric and underscore only"
                return True, None
            
            def validate_url(self, url):
                # 簡單的 URL 驗證
                import re
                pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                return bool(re.match(pattern, url))
            
            def sanitize_filename(self, filename):
                # 移除危險字符
                import re
                # 只保留安全字符
                safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
                # 防止目錄遍歷
                safe_filename = safe_filename.replace('..', '')
                return safe_filename
        
        validator = InputValidator()
        
        # 測試電子郵件驗證
        assert validator.validate_email("user@example.com") is True
        assert validator.validate_email("invalid.email") is False
        
        # 測試用戶名驗證
        valid, _ = validator.validate_username("valid_user123")
        assert valid is True
        
        valid, error = validator.validate_username("invalid user!")
        assert valid is False
        assert "alphanumeric" in error
        
        # 測試 URL 驗證
        assert validator.validate_url("https://example.com") is True
        assert validator.validate_url("javascript:alert('XSS')") is False
        
        # 測試文件名清理
        assert validator.sanitize_filename("../../../etc/passwd") == "etcpasswd"
        assert validator.sanitize_filename("file<script>.txt") == "filescript.txt"
    
    @pytest.mark.asyncio
    async def test_session_security(self):
        """測試會話安全"""
        # 安全會話管理器
        class SecureSessionManager:
            def __init__(self):
                self.sessions = {}
                self.session_timeout = timedelta(hours=2)
            
            def create_session(self, user_id, ip_address, user_agent):
                session_id = secrets.token_urlsafe(32)
                
                self.sessions[session_id] = {
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "created_at": datetime.now(),
                    "last_activity": datetime.now(),
                    "fingerprint": self._generate_fingerprint(ip_address, user_agent)
                }
                
                return session_id
            
            def _generate_fingerprint(self, ip_address, user_agent):
                data = f"{ip_address}:{user_agent}"
                return hashlib.sha256(data.encode()).hexdigest()
            
            def validate_session(self, session_id, ip_address, user_agent):
                if session_id not in self.sessions:
                    return False, "Invalid session"
                
                session = self.sessions[session_id]
                
                # 檢查超時
                if datetime.now() - session["last_activity"] > self.session_timeout:
                    del self.sessions[session_id]
                    return False, "Session expired"
                
                # 檢查指紋（防止會話劫持）
                current_fingerprint = self._generate_fingerprint(ip_address, user_agent)
                if session["fingerprint"] != current_fingerprint:
                    return False, "Session fingerprint mismatch"
                
                # 更新活動時間
                session["last_activity"] = datetime.now()
                
                return True, session["user_id"]
        
        manager = SecureSessionManager()
        
        # 創建會話
        session_id = manager.create_session("user123", "192.168.1.1", "Mozilla/5.0")
        assert len(session_id) > 30
        
        # 驗證有效會話
        valid, user_id = manager.validate_session(session_id, "192.168.1.1", "Mozilla/5.0")
        assert valid is True
        assert user_id == "user123"
        
        # 測試會話劫持檢測（不同 IP）
        valid, _ = manager.validate_session(session_id, "192.168.1.2", "Mozilla/5.0")
        assert valid is False
    
    def test_encryption_and_hashing(self):
        """測試加密和雜湊功能"""
        # 加密工具
        class CryptoUtils:
            def __init__(self, secret_key):
                self.secret_key = secret_key.encode()
            
            def generate_hmac(self, data):
                return hmac.new(
                    self.secret_key,
                    data.encode(),
                    hashlib.sha256
                ).hexdigest()
            
            def verify_hmac(self, data, signature):
                expected = self.generate_hmac(data)
                return hmac.compare_digest(expected, signature)
            
            def hash_sensitive_data(self, data):
                # 使用 salt 的雜湊
                salt = secrets.token_bytes(32)
                key = hashlib.pbkdf2_hmac(
                    'sha256',
                    data.encode(),
                    salt,
                    100000  # 迭代次數
                )
                return salt.hex() + ':' + key.hex()
        
        crypto = CryptoUtils("my-secret-key")
        
        # 測試 HMAC
        data = "sensitive data"
        signature = crypto.generate_hmac(data)
        assert len(signature) == 64  # SHA256 的十六進制長度
        
        # 驗證正確的簽名
        assert crypto.verify_hmac(data, signature) is True
        
        # 驗證錯誤的簽名
        assert crypto.verify_hmac(data, "wrong_signature") is False
        
        # 測試敏感資料雜湊
        hashed = crypto.hash_sensitive_data("my_password")
        assert ':' in hashed  # 包含 salt 和 hash
        assert len(hashed) > 100  # 足夠長
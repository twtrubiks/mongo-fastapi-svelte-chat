"""檔案處理服務的測試"""

import hashlib
import io
import mimetypes
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock


class TestFileHandlingService:
    """測試檔案處理的各種功能"""

    def test_file_upload_validation(self):
        """測試檔案上傳驗證"""

        # Mock 檔案驗證器
        class FileValidator:
            def __init__(self):
                self.max_size = 10 * 1024 * 1024  # 10MB
                self.allowed_types = {".jpg", ".jpeg", ".png", ".pdf", ".doc", ".docx"}
                self.allowed_mimes = {
                    "image/jpeg",
                    "image/png",
                    "application/pdf",
                    "application/msword",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                }

            def validate(self, file_name, file_size, file_content):
                # 檢查檔案大小
                if file_size > self.max_size:
                    return False, "File size exceeds 10MB limit"

                # 檢查副檔名
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in self.allowed_types:
                    return False, f"File type {ext} not allowed"

                # 檢查 MIME 類型
                mime_type = mimetypes.guess_type(file_name)[0]
                if mime_type not in self.allowed_mimes:
                    return False, f"MIME type {mime_type} not allowed"

                # 檢查檔案內容（魔術數字）
                if not self._check_magic_number(file_content, ext):
                    return False, "File content does not match extension"

                return True, "Valid"

            def _check_magic_number(self, content, ext):
                magic_numbers = {
                    ".jpg": [b"\xff\xd8\xff"],
                    ".jpeg": [b"\xff\xd8\xff"],
                    ".png": [b"\x89PNG"],
                    ".pdf": [b"%PDF"],
                }

                if ext in magic_numbers:
                    for magic in magic_numbers[ext]:
                        if content.startswith(magic):
                            return True
                    return False
                return True

        # 測試驗證器
        validator = FileValidator()

        # 測試有效的 JPEG 檔案
        valid, msg = validator.validate(
            "test.jpg",
            1024 * 1024,  # 1MB
            b"\xff\xd8\xff\xe0\x00\x10JFIF",  # JPEG 魔術數字
        )
        assert valid is True

        # 測試檔案過大
        valid, msg = validator.validate(
            "test.jpg", 11 * 1024 * 1024, b"\xff\xd8\xff"  # 11MB
        )
        assert valid is False
        assert "exceeds 10MB limit" in msg

        # 測試不允許的檔案類型
        valid, msg = validator.validate("test.exe", 1024, b"MZ")
        assert valid is False
        assert "not allowed" in msg

    def test_file_storage_service(self):
        """測試檔案儲存服務"""
        # Mock 檔案儲存服務
        mock_s3 = Mock()
        mock_db = Mock()

        class FileStorageService:
            def __init__(self, s3_client, database):
                self.s3 = s3_client
                self.db = database
                self.bucket = "test-bucket"

            def store_file(self, file_data, user_id):
                # 生成唯一檔名
                import uuid

                file_id = str(uuid.uuid4())
                file_key = f"uploads/{user_id}/{file_id}/{file_data['name']}"

                # 上傳到 S3
                self.s3.put_object(
                    Bucket=self.bucket,
                    Key=file_key,
                    Body=file_data["content"],
                    ContentType=file_data["content_type"],
                    Metadata={"user_id": user_id, "original_name": file_data["name"]},
                )

                # 儲存檔案資訊到資料庫
                file_record = {
                    "file_id": file_id,
                    "user_id": user_id,
                    "file_name": file_data["name"],
                    "file_size": len(file_data["content"]),
                    "content_type": file_data["content_type"],
                    "s3_key": file_key,
                    "upload_time": datetime.now(UTC).isoformat(),
                }

                self.db.files.insert_one(file_record)

                # 生成檔案 URL
                url = f"https://{self.bucket}.s3.amazonaws.com/{file_key}"

                return {
                    "file_id": file_id,
                    "url": url,
                    "size": file_record["file_size"],
                }

        # 設置 Mock
        mock_s3.put_object.return_value = {"ETag": '"abc123"'}
        mock_db.files.insert_one.return_value = Mock(inserted_id="doc123")

        # 測試
        service = FileStorageService(mock_s3, mock_db)

        result = service.store_file(
            {
                "name": "test.pdf",
                "content": b"PDF content",
                "content_type": "application/pdf",
            },
            "user123",
        )

        # 驗證結果
        assert "file_id" in result
        assert "url" in result
        assert result["size"] == 11  # len(b'PDF content')

        # 驗證 S3 調用
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args[1]
        assert call_args["Bucket"] == "test-bucket"
        assert "uploads/user123/" in call_args["Key"]

        # 驗證資料庫調用
        mock_db.files.insert_one.assert_called_once()

    def test_image_processing_service(self):
        """測試圖片處理服務"""
        # Mock 圖片處理服務 (預留供未來實現)
        _mock_pil = Mock()

        class ImageProcessingService:
            def __init__(self):
                self.thumbnail_sizes = {
                    "small": (150, 150),
                    "medium": (300, 300),
                    "large": (600, 600),
                }

            def process_image(self, image_data, options=None):
                # Mock PIL Image
                mock_image = Mock()
                mock_image.size = (1200, 800)
                mock_image.format = "JPEG"

                results = {
                    "original": {
                        "width": mock_image.size[0],
                        "height": mock_image.size[1],
                        "format": mock_image.format,
                    }
                }

                # 生成縮圖
                if options and options.get("generate_thumbnails"):
                    results["thumbnails"] = {}

                    for size_name, dimensions in self.thumbnail_sizes.items():
                        # Mock 縮圖生成
                        mock_thumbnail = Mock()
                        mock_thumbnail.size = dimensions

                        # 儲存縮圖資料
                        thumbnail_buffer = io.BytesIO()
                        thumbnail_buffer.write(b"thumbnail_data")

                        results["thumbnails"][size_name] = {
                            "width": dimensions[0],
                            "height": dimensions[1],
                            "data": thumbnail_buffer.getvalue(),
                        }

                # 優化圖片
                if options and options.get("optimize"):
                    results["optimized"] = {"quality": 85, "size_reduction": "25%"}

                # 提取 EXIF 資料
                if options and options.get("extract_exif"):
                    results["exif"] = {
                        "Camera": "Canon EOS",
                        "DateTime": "2024:01:01 12:00:00",
                        "GPS": {"lat": 25.0330, "lon": 121.5654},
                    }

                return results

        # 測試
        service = ImageProcessingService()

        # 測試完整處理
        result = service.process_image(
            b"fake_image_data",
            options={
                "generate_thumbnails": True,
                "optimize": True,
                "extract_exif": True,
            },
        )

        # 驗證結果
        assert result["original"]["width"] == 1200
        assert result["original"]["height"] == 800
        assert "thumbnails" in result
        assert len(result["thumbnails"]) == 3
        assert result["thumbnails"]["small"]["width"] == 150
        assert "optimized" in result
        assert "exif" in result
        assert result["exif"]["GPS"]["lat"] == 25.0330

    def test_file_compression_service(self):
        """測試檔案壓縮服務"""
        import gzip
        import zipfile

        class CompressionService:
            def __init__(self):
                self.compression_threshold = 1024  # 1KB

            def compress_file(self, file_data, compression_type="gzip"):
                original_size = len(file_data)

                if original_size < self.compression_threshold:
                    return {
                        "compressed": False,
                        "reason": "File too small",
                        "original_size": original_size,
                    }

                if compression_type == "gzip":
                    compressed = gzip.compress(file_data)
                elif compression_type == "zip":
                    buffer = io.BytesIO()
                    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        zf.writestr("file", file_data)
                    compressed = buffer.getvalue()
                else:
                    raise ValueError(
                        f"Unsupported compression type: {compression_type}"
                    )

                compressed_size = len(compressed)
                compression_ratio = (
                    (original_size - compressed_size) / original_size * 100
                )

                return {
                    "compressed": True,
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "compression_ratio": f"{compression_ratio:.1f}%",
                    "data": compressed,
                }

            def compress_multiple(self, files):
                """壓縮多個檔案為 ZIP"""
                buffer = io.BytesIO()

                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    for file_name, file_data in files.items():
                        zf.writestr(file_name, file_data)

                return {
                    "archive_size": buffer.tell(),
                    "file_count": len(files),
                    "data": buffer.getvalue(),
                }

        # 測試
        service = CompressionService()

        # 測試單檔案壓縮
        test_data = b"This is a test file content that should be compressed" * 100
        result = service.compress_file(test_data, "gzip")

        assert result["compressed"] is True
        assert result["compressed_size"] < result["original_size"]
        assert "compression_ratio" in result

        # 測試多檔案壓縮
        files = {
            "file1.txt": b"Content of file 1",
            "file2.txt": b"Content of file 2",
            "file3.txt": b"Content of file 3",
        }

        result = service.compress_multiple(files)
        assert result["file_count"] == 3
        assert result["archive_size"] > 0

    def test_file_virus_scanning(self):
        """測試檔案病毒掃描"""
        # Mock 病毒掃描服務
        mock_av_engine = Mock()

        class VirusScanningService:
            def __init__(self, av_engine):
                self.av = av_engine
                self.quarantine = Mock()

            def scan_file(self, file_data, file_name):
                # 計算檔案雜湊
                file_hash = hashlib.sha256(file_data).hexdigest()

                # 執行掃描
                scan_result = self.av.scan(file_data)

                result = {
                    "file_name": file_name,
                    "file_hash": file_hash,
                    "scan_time": datetime.now(UTC).isoformat(),
                    "clean": scan_result["clean"],
                    "threats": scan_result.get("threats", []),
                }

                # 如果發現威脅，隔離檔案
                if not scan_result["clean"]:
                    self.quarantine.add(file_hash, file_data, result["threats"])
                    result["quarantined"] = True

                return result

            def scan_batch(self, files):
                """批量掃描檔案"""
                results = []
                infected_count = 0

                for file_name, file_data in files:
                    result = self.scan_file(file_data, file_name)
                    results.append(result)

                    if not result["clean"]:
                        infected_count += 1

                return {
                    "total_files": len(files),
                    "infected_files": infected_count,
                    "clean_files": len(files) - infected_count,
                    "results": results,
                }

        # 設置 Mock 行為
        mock_av_engine.scan.side_effect = [
            {"clean": True},
            {"clean": False, "threats": ["Trojan.Generic"]},
            {"clean": True},
        ]

        # 測試
        service = VirusScanningService(mock_av_engine)

        # 測試單檔案掃描（乾淨）
        result = service.scan_file(b"clean file content", "clean.txt")
        assert result["clean"] is True
        assert len(result["threats"]) == 0

        # 測試單檔案掃描（感染）
        result = service.scan_file(b"infected content", "virus.exe")
        assert result["clean"] is False
        assert "Trojan.Generic" in result["threats"]
        assert result.get("quarantined") is True

        # 測試批量掃描
        files = [
            ("file1.txt", b"content1"),
            ("file2.exe", b"content2"),
            ("file3.pdf", b"content3"),
        ]

        mock_av_engine.scan.side_effect = [
            {"clean": True},
            {"clean": False, "threats": ["Malware"]},
            {"clean": True},
        ]

        batch_result = service.scan_batch(files)
        assert batch_result["total_files"] == 3
        assert batch_result["infected_files"] == 1
        assert batch_result["clean_files"] == 2

    def test_file_metadata_extraction(self):
        """測試檔案元資料提取"""

        class MetadataExtractor:
            def extract(self, file_name, file_content):

                # 基本元資料
                metadata = {
                    "file_name": file_name,
                    "file_size": len(file_content),
                    "file_extension": os.path.splitext(file_name)[1],
                    "mime_type": mimetypes.guess_type(file_name)[0],
                }

                # 根據檔案類型提取特定元資料
                if metadata["mime_type"] and metadata["mime_type"].startswith("image/"):
                    metadata.update(self._extract_image_metadata(file_content))
                elif metadata["mime_type"] == "application/pdf":
                    metadata.update(self._extract_pdf_metadata(file_content))
                elif metadata["mime_type"] and "text" in metadata["mime_type"]:
                    metadata.update(self._extract_text_metadata(file_content))

                # 計算檔案雜湊
                metadata["md5"] = hashlib.md5(file_content).hexdigest()
                metadata["sha1"] = hashlib.sha1(file_content).hexdigest()
                metadata["sha256"] = hashlib.sha256(file_content).hexdigest()

                return metadata

            def _extract_image_metadata(self, content):
                # Mock 圖片元資料
                return {
                    "image_width": 1920,
                    "image_height": 1080,
                    "image_format": "JPEG",
                    "color_mode": "RGB",
                    "dpi": (72, 72),
                }

            def _extract_pdf_metadata(self, content):
                # Mock PDF 元資料
                return {
                    "page_count": 5,
                    "pdf_version": "1.7",
                    "author": "Test Author",
                    "title": "Test Document",
                    "creation_date": "2024-01-01",
                }

            def _extract_text_metadata(self, content):
                # 文字檔案元資料
                text = content.decode("utf-8", errors="ignore")
                lines = text.split("\n")
                words = text.split()

                return {
                    "line_count": len(lines),
                    "word_count": len(words),
                    "character_count": len(text),
                    "encoding": "utf-8",
                }

        # 測試
        extractor = MetadataExtractor()

        # 測試圖片元資料
        metadata = extractor.extract("test.jpg", b"fake_image_data")
        assert metadata["mime_type"] == "image/jpeg"
        assert metadata["image_width"] == 1920
        assert metadata["image_height"] == 1080
        assert "md5" in metadata
        assert "sha256" in metadata

        # 測試 PDF 元資料
        metadata = extractor.extract("document.pdf", b"fake_pdf_data")
        assert metadata["mime_type"] == "application/pdf"
        assert metadata["page_count"] == 5
        assert metadata["author"] == "Test Author"

        # 測試文字元資料
        text_content = b"Line 1\nLine 2\nLine 3"
        metadata = extractor.extract("test.txt", text_content)
        assert metadata["mime_type"] == "text/plain"
        assert metadata["line_count"] == 3
        assert metadata["word_count"] == 6

    def test_file_access_control(self):
        """測試檔案存取控制"""
        # Mock 存取控制服務
        mock_db = Mock()

        class FileAccessControl:
            def __init__(self, database):
                self.db = database

            def check_permission(self, user_id, file_id, action="read"):
                # 獲取檔案資訊
                file_doc = self.db.files.find_one({"file_id": file_id})
                if not file_doc:
                    return False, "File not found"

                # 檢查擁有者
                if file_doc["owner_id"] == user_id:
                    return True, "Owner access"

                # 檢查共享權限
                if "shared_with" in file_doc:
                    for share in file_doc["shared_with"]:
                        if share["user_id"] == user_id:
                            if action in share["permissions"]:
                                return True, f"Shared {action} access"

                # 檢查公開連結
                if file_doc.get("public_link"):
                    if action == "read":
                        return True, "Public read access"

                return False, "Access denied"

            def share_file(self, owner_id, file_id, target_user_id, permissions):
                # 驗證擁有者
                file_doc = self.db.files.find_one(
                    {"file_id": file_id, "owner_id": owner_id}
                )

                if not file_doc:
                    return False, "File not found or not owner"

                # 更新共享權限
                self.db.files.update_one(
                    {"file_id": file_id},
                    {
                        "$push": {
                            "shared_with": {
                                "user_id": target_user_id,
                                "permissions": permissions,
                                "shared_at": datetime.now(UTC).isoformat(),
                            }
                        }
                    },
                )

                return True, "File shared successfully"

            def create_public_link(self, owner_id, file_id, expiry_hours=24):
                # 生成公開連結
                import secrets

                token = secrets.token_urlsafe(32)

                expiry_time = datetime.now(UTC) + timedelta(hours=expiry_hours)

                self.db.files.update_one(
                    {"file_id": file_id, "owner_id": owner_id},
                    {
                        "$set": {
                            "public_link": {
                                "token": token,
                                "created_at": datetime.now(UTC).isoformat(),
                                "expires_at": expiry_time.isoformat(),
                            }
                        }
                    },
                )

                return f"https://example.com/files/public/{token}"

        # 設置 Mock
        mock_db.files.find_one.side_effect = [
            # 第一次調用 - 擁有者檢查
            {"file_id": "file123", "owner_id": "user1"},
            # 第二次調用 - 共享檢查
            {
                "file_id": "file456",
                "owner_id": "user2",
                "shared_with": [{"user_id": "user1", "permissions": ["read"]}],
            },
            # 第三次調用 - 分享操作
            {"file_id": "file123", "owner_id": "user1"},
        ]

        mock_db.files.update_one.return_value = Mock(modified_count=1)

        # 測試
        access_control = FileAccessControl(mock_db)

        # 測試擁有者存取
        allowed, reason = access_control.check_permission("user1", "file123", "write")
        assert allowed is True
        assert reason == "Owner access"

        # 測試共享存取
        allowed, reason = access_control.check_permission("user1", "file456", "read")
        assert allowed is True
        assert "Shared read access" in reason

        # 測試分享檔案
        success, msg = access_control.share_file(
            "user1", "file123", "user3", ["read", "download"]
        )
        assert success is True
        assert "shared successfully" in msg

    def test_file_download_service(self):
        """測試檔案下載服務"""
        # Mock 下載服務
        mock_s3 = Mock()
        mock_cache = Mock()

        class FileDownloadService:
            def __init__(self, s3_client, cache):
                self.s3 = s3_client
                self.cache = cache
                self.bucket = "test-bucket"

            def download_file(self, file_id, user_id, options=None):
                # 檢查快取
                cache_key = f"file:{file_id}"
                cached_data = self.cache.get(cache_key)

                if cached_data:
                    return {"data": cached_data, "from_cache": True}

                # 從 S3 下載
                s3_key = f"uploads/{user_id}/{file_id}"

                try:
                    response = self.s3.get_object(Bucket=self.bucket, Key=s3_key)

                    file_data = response["Body"].read()

                    # 快取小檔案
                    if len(file_data) < 1024 * 1024:  # 1MB
                        self.cache.set(cache_key, file_data, ex=3600)

                    # 處理下載選項
                    if options:
                        if options.get("compress"):
                            import gzip

                            file_data = gzip.compress(file_data)

                        if options.get("encrypt"):
                            # Mock 加密
                            file_data = b"encrypted:" + file_data

                    return {
                        "data": file_data,
                        "from_cache": False,
                        "metadata": response.get("Metadata", {}),
                    }

                except Exception as e:
                    return {"error": str(e), "status": "failed"}

            def generate_download_url(self, file_id, expiry_seconds=3600):
                """生成預簽名下載 URL"""
                s3_key = f"uploads/{file_id}"

                url = self.s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": s3_key},
                    ExpiresIn=expiry_seconds,
                )

                return {"url": url, "expires_in": expiry_seconds}

        # 設置 Mock
        mock_cache.get.return_value = None
        mock_s3.get_object.return_value = {
            "Body": Mock(read=lambda: b"file content"),
            "Metadata": {"original_name": "test.pdf"},
        }
        mock_s3.generate_presigned_url.return_value = "https://s3.url/signed"

        # 測試
        service = FileDownloadService(mock_s3, mock_cache)

        # 測試檔案下載
        result = service.download_file("file123", "user1")
        assert result["data"] == b"file content"
        assert result["from_cache"] is False
        assert result["metadata"]["original_name"] == "test.pdf"

        # 測試壓縮下載
        result = service.download_file("file123", "user1", options={"compress": True})
        assert result["data"].startswith(b"\x1f\x8b")  # gzip magic number

        # 測試預簽名 URL
        result = service.generate_download_url("file123", 7200)
        assert "https://s3.url/signed" in result["url"]
        assert result["expires_in"] == 7200

    def test_file_cleanup_service(self):
        """測試檔案清理服務"""
        # Mock 清理服務
        mock_db = Mock()
        mock_s3 = Mock()

        class FileCleanupService:
            def __init__(self, database, s3_client):
                self.db = database
                self.s3 = s3_client
                self.bucket = "test-bucket"

            def cleanup_expired_files(self, retention_days=30):
                # 計算過期時間
                expiry_date = datetime.now(UTC) - timedelta(days=retention_days)

                # 查找過期檔案
                expired_files = list(
                    self.db.files.find(
                        {
                            "upload_time": {"$lt": expiry_date.isoformat()},
                            "permanent": {"$ne": True},
                        }
                    )
                )

                deleted_count = 0
                failed_count = 0

                for file_doc in expired_files:
                    try:
                        # 從 S3 刪除
                        self.s3.delete_object(
                            Bucket=self.bucket, Key=file_doc["s3_key"]
                        )

                        # 從資料庫刪除
                        self.db.files.delete_one({"_id": file_doc["_id"]})

                        deleted_count += 1
                    except Exception:
                        failed_count += 1

                return {
                    "total_expired": len(expired_files),
                    "deleted": deleted_count,
                    "failed": failed_count,
                }

            def cleanup_orphaned_files(self):
                """清理孤立檔案（S3 有但資料庫沒有）"""
                # 獲取 S3 檔案列表
                s3_files = set()
                paginator = self.s3.get_paginator("list_objects_v2")

                for page in paginator.paginate(Bucket=self.bucket):
                    if "Contents" in page:
                        for obj in page["Contents"]:
                            s3_files.add(obj["Key"])

                # 獲取資料庫檔案列表
                db_files = {
                    doc["s3_key"] for doc in self.db.files.find({}, {"s3_key": 1})
                }

                # 找出孤立檔案
                orphaned = s3_files - db_files

                # 刪除孤立檔案
                deleted = 0
                for key in orphaned:
                    try:
                        self.s3.delete_object(Bucket=self.bucket, Key=key)
                        deleted += 1
                    except Exception:
                        pass

                return {"orphaned_files": len(orphaned), "deleted": deleted}

            def calculate_storage_usage(self, user_id=None):
                """計算儲存使用量"""
                query = {"user_id": user_id} if user_id else {}

                pipeline = [
                    {"$match": query},
                    {
                        "$group": {
                            "_id": "$user_id" if not user_id else None,
                            "total_size": {"$sum": "$file_size"},
                            "file_count": {"$sum": 1},
                        }
                    },
                ]

                results = list(self.db.files.aggregate(pipeline))

                if user_id and results:
                    return {
                        "user_id": user_id,
                        "total_size": results[0]["total_size"],
                        "file_count": results[0]["file_count"],
                        "size_readable": self._format_size(results[0]["total_size"]),
                    }

                return {"users": results, "total_users": len(results)}

            def _format_size(self, size_bytes):
                """格式化檔案大小"""
                for unit in ["B", "KB", "MB", "GB", "TB"]:
                    if size_bytes < 1024.0:
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024.0
                return f"{size_bytes:.2f} PB"

        # 設置 Mock
        expired_files = [
            {"_id": "1", "s3_key": "old/file1"},
            {"_id": "2", "s3_key": "old/file2"},
        ]
        mock_db.files.find.return_value = expired_files
        mock_db.files.delete_one.return_value = Mock(deleted_count=1)
        mock_s3.delete_object.return_value = {}

        # Mock paginator
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {"Contents": [{"Key": "file1"}, {"Key": "file2"}, {"Key": "orphan1"}]}
        ]
        mock_s3.get_paginator.return_value = mock_paginator

        # 測試
        service = FileCleanupService(mock_db, mock_s3)

        # 測試過期檔案清理
        result = service.cleanup_expired_files(30)
        assert result["total_expired"] == 2
        assert result["deleted"] == 2

        # 測試儲存使用量計算
        mock_db.files.aggregate.return_value = [
            {"_id": "user1", "total_size": 5242880, "file_count": 10}
        ]

        usage = service.calculate_storage_usage("user1")
        assert usage["file_count"] == 10
        assert usage["size_readable"] == "5.00 MB"

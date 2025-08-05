"""檔案上傳工具"""
import os
import uuid
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import aiofiles
import logging

logger = logging.getLogger(__name__)

# 允許的檔案類型
ALLOWED_FILE_TYPES = {
    'image': {
        'extensions': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
        'mime_types': ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'],
        'max_size': 10 * 1024 * 1024  # 10MB
    },
    'document': {
        'extensions': ['.pdf', '.doc', '.docx', '.txt', '.md'],
        'mime_types': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/markdown'],
        'max_size': 50 * 1024 * 1024  # 50MB
    },
    'video': {
        'extensions': ['.mp4', '.mov', '.avi', '.mkv', '.webm'],
        'mime_types': ['video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/x-matroska', 'video/webm'],
        'max_size': 100 * 1024 * 1024  # 100MB
    },
    'audio': {
        'extensions': ['.mp3', '.wav', '.ogg', '.m4a', '.flac'],
        'mime_types': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp4', 'audio/flac'],
        'max_size': 20 * 1024 * 1024  # 20MB
    }
}


class FileUploadError(Exception):
    """檔案上傳錯誤"""
    pass


class FileUploadManager:
    """檔案上傳管理器"""
    
    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
        
        # 創建不同類型的子目錄
        for file_type in ALLOWED_FILE_TYPES.keys():
            (self.upload_dir / file_type).mkdir(exist_ok=True)
    
    def get_file_type(self, file: UploadFile) -> str:
        """
        根據檔案擴展名和 MIME 類型判斷檔案類型
        
        Args:
            file: 上傳的檔案
            
        Returns:
            str: 檔案類型
            
        Raises:
            FileUploadError: 不支援的檔案類型
        """
        file_ext = Path(file.filename).suffix.lower()
        mime_type = file.content_type
        
        for file_type, config in ALLOWED_FILE_TYPES.items():
            if file_ext in config['extensions'] or mime_type in config['mime_types']:
                return file_type
        
        raise FileUploadError(f"不支援的檔案類型: {file_ext} ({mime_type})")
    
    def validate_file(self, file: UploadFile) -> Tuple[str, Dict[str, Any]]:
        """
        驗證檔案
        
        Args:
            file: 上傳的檔案
            
        Returns:
            Tuple[str, Dict[str, Any]]: 檔案類型和驗證資訊
            
        Raises:
            FileUploadError: 檔案驗證失敗
        """
        if not file.filename:
            raise FileUploadError("檔案名稱不能為空")
        
        # 獲取檔案類型
        file_type = self.get_file_type(file)
        config = ALLOWED_FILE_TYPES[file_type]
        
        # 檢查檔案大小
        if file.size and file.size > config['max_size']:
            max_size_mb = config['max_size'] / (1024 * 1024)
            raise FileUploadError(f"檔案大小超過限制 ({max_size_mb:.1f}MB)")
        
        # 檢查檔案名稱長度
        if len(file.filename) > 255:
            raise FileUploadError("檔案名稱太長")
        
        # 檢查檔案名稱字符
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        if any(char in file.filename for char in invalid_chars):
            raise FileUploadError("檔案名稱包含不允許的字符")
        
        validation_info = {
            'file_type': file_type,
            'original_name': file.filename,
            'content_type': file.content_type,
            'size': file.size
        }
        
        return file_type, validation_info
    
    def generate_unique_filename(self, original_filename: str) -> str:
        """
        生成唯一的檔案名稱
        
        Args:
            original_filename: 原始檔案名稱
            
        Returns:
            str: 唯一的檔案名稱
        """
        file_ext = Path(original_filename).suffix.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        return f"{timestamp}_{unique_id}{file_ext}"
    
    async def get_file_hash(self, file_path: Path) -> str:
        """
        計算檔案雜湊值
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            str: 檔案的 SHA-256 雜湊值
        """
        sha256_hash = hashlib.sha256()
        async with aiofiles.open(file_path, "rb") as f:
            while chunk := await f.read(4096):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    async def save_file(
        self,
        file: UploadFile,
        custom_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        儲存檔案
        
        Args:
            file: 上傳的檔案
            custom_filename: 自定義檔案名稱（可選）
            
        Returns:
            Dict[str, Any]: 儲存的檔案資訊
            
        Raises:
            FileUploadError: 檔案儲存失敗
        """
        try:
            # 驗證檔案
            file_type, validation_info = self.validate_file(file)
            
            # 生成檔案名稱
            if custom_filename:
                filename = custom_filename
            else:
                filename = self.generate_unique_filename(file.filename)
            
            # 確定儲存路徑
            file_dir = self.upload_dir / file_type
            file_path = file_dir / filename
            
            # 確保目錄存在
            file_dir.mkdir(parents=True, exist_ok=True)
            
            # 儲存檔案
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            # 計算檔案雜湊值
            file_hash = await self.get_file_hash(file_path)
            
            # 獲取檔案資訊
            file_info = {
                'id': str(uuid.uuid4()),
                'filename': filename,
                'original_name': validation_info['original_name'],
                'file_type': file_type,
                'content_type': validation_info['content_type'],
                'size': os.path.getsize(file_path),
                'hash': file_hash,
                'path': str(file_path),
                'relative_path': f"{file_type}/{filename}",
                'url': f"/api/files/{file_type}/{filename}",
                'created_at': datetime.now(UTC)
            }
            
            logger.info(f"File uploaded successfully: {filename}")
            return file_info
            
        except Exception as e:
            logger.error(f"Error saving file: {e}")
            raise FileUploadError(f"檔案儲存失敗: {str(e)}")
    
    async def save_multiple_files(
        self,
        files: List[UploadFile],
        max_files: int = 10
    ) -> List[Dict[str, Any]]:
        """
        儲存多個檔案
        
        Args:
            files: 上傳的檔案列表
            max_files: 最大檔案數量
            
        Returns:
            List[Dict[str, Any]]: 儲存的檔案資訊列表
            
        Raises:
            FileUploadError: 檔案儲存失敗
        """
        if len(files) > max_files:
            raise FileUploadError(f"檔案數量超過限制 ({max_files})")
        
        saved_files = []
        
        for file in files:
            try:
                file_info = await self.save_file(file)
                saved_files.append(file_info)
            except FileUploadError as e:
                logger.error(f"Error saving file {file.filename}: {e}")
                # 清理已儲存的檔案
                for saved_file in saved_files:
                    try:
                        os.remove(saved_file['path'])
                    except:
                        pass
                raise
        
        return saved_files
    
    def delete_file(self, file_path: str) -> bool:
        """
        刪除檔案
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            bool: 是否成功刪除
        """
        try:
            full_path = self.upload_dir / file_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"File deleted: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return False
    
    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        獲取檔案資訊
        
        Args:
            file_path: 檔案路徑
            
        Returns:
            Optional[Dict[str, Any]]: 檔案資訊
        """
        try:
            full_path = self.upload_dir / file_path
            if not full_path.exists():
                return None
            
            stat = full_path.stat()
            
            return {
                'filename': full_path.name,
                'size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'path': str(full_path),
                'relative_path': file_path,
                'exists': True
            }
        except Exception as e:
            logger.error(f"Error getting file info {file_path}: {e}")
            return None
    
    def check_duplicate_file(self, file_hash: str) -> Optional[str]:
        """
        檢查重複檔案
        
        Args:
            file_hash: 檔案雜湊值
            
        Returns:
            Optional[str]: 重複檔案的路徑，如果沒有重複則返回 None
        """
        # 這裡可以實現檔案去重邏輯
        # 例如維護一個檔案雜湊值和路徑的映射
        # 暫時返回 None，表示不檢查重複
        return None
    
    def get_upload_stats(self) -> Dict[str, Any]:
        """
        獲取上傳統計
        
        Returns:
            Dict[str, Any]: 上傳統計資訊
        """
        stats = {
            'total_files': 0,
            'total_size': 0,
            'file_types': {}
        }
        
        for file_type in ALLOWED_FILE_TYPES.keys():
            type_dir = self.upload_dir / file_type
            if type_dir.exists():
                files = list(type_dir.iterdir())
                file_count = len(files)
                total_size = sum(f.stat().st_size for f in files if f.is_file())
                
                stats['file_types'][file_type] = {
                    'count': file_count,
                    'size': total_size
                }
                
                stats['total_files'] += file_count
                stats['total_size'] += total_size
        
        return stats
    
    def cleanup_old_files(self, days: int = 30) -> int:
        """
        清理舊檔案
        
        Args:
            days: 保留天數
            
        Returns:
            int: 清理的檔案數量
        """
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)
        deleted_count = 0
        
        for file_type in ALLOWED_FILE_TYPES.keys():
            type_dir = self.upload_dir / file_type
            if type_dir.exists():
                for file_path in type_dir.iterdir():
                    if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                        try:
                            file_path.unlink()
                            deleted_count += 1
                            logger.info(f"Cleaned up old file: {file_path}")
                        except Exception as e:
                            logger.error(f"Error cleaning up file {file_path}: {e}")
        
        return deleted_count


# 全域檔案上傳管理器實例
file_upload_manager = FileUploadManager()


def get_file_upload_manager() -> FileUploadManager:
    """獲取檔案上傳管理器實例"""
    return file_upload_manager


async def upload_file(
    file: UploadFile,
    allowed_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    上傳單個檔案的便捷函數
    
    Args:
        file: 上傳的檔案
        allowed_types: 允許的檔案類型列表
        
    Returns:
        Dict[str, Any]: 上傳的檔案資訊
        
    Raises:
        HTTPException: 檔案上傳失敗
    """
    try:
        manager = get_file_upload_manager()
        
        # 如果指定了允許的類型，進行額外檢查
        if allowed_types:
            file_type = manager.get_file_type(file)
            if file_type not in allowed_types:
                raise FileUploadError(f"不允許的檔案類型: {file_type}")
        
        return await manager.save_file(file)
        
    except FileUploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in upload_file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="檔案上傳失敗"
        )


async def upload_multiple_files(
    files: List[UploadFile],
    allowed_types: Optional[List[str]] = None,
    max_files: int = 10
) -> List[Dict[str, Any]]:
    """
    上傳多個檔案的便捷函數
    
    Args:
        files: 上傳的檔案列表
        allowed_types: 允許的檔案類型列表
        max_files: 最大檔案數量
        
    Returns:
        List[Dict[str, Any]]: 上傳的檔案資訊列表
        
    Raises:
        HTTPException: 檔案上傳失敗
    """
    try:
        manager = get_file_upload_manager()
        
        # 如果指定了允許的類型，進行額外檢查
        if allowed_types:
            for file in files:
                file_type = manager.get_file_type(file)
                if file_type not in allowed_types:
                    raise FileUploadError(f"不允許的檔案類型: {file_type} ({file.filename})")
        
        return await manager.save_multiple_files(files, max_files)
        
    except FileUploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in upload_multiple_files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="檔案上傳失敗"
        )


def cleanup_file(file_path: str) -> bool:
    """
    清理指定檔案（向後兼容函數）
    
    Args:
        file_path: 要清理的檔案路徑
        
    Returns:
        bool: 清理是否成功
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Successfully cleaned up file: {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to cleanup file {file_path}: {e}")
        return False
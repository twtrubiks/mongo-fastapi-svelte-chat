"""資料庫連線相關例外"""


class NotConnectedError(RuntimeError):
    """MongoDB / Redis 尚未連線（啟動或重連的空檔）

    繼承 RuntimeError 維持既有行為；獨立型別讓呼叫端能把它當成暫時故障處理
    （例如 WS 認證不把它當成認證失敗）。
    """

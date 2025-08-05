"""日期時間工具"""
import pytz
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List, Tuple
from dateutil import parser
from dateutil.relativedelta import relativedelta
import calendar
import logging

UTC = timezone.utc

logger = logging.getLogger(__name__)


class DateTimeError(Exception):
    """日期時間相關錯誤"""
    pass


class DateTimeUtils:
    """日期時間工具類別"""
    
    # 常用時區
    TIMEZONES = {
        'UTC': 'UTC',
        'Asia/Taipei': 'Asia/Taipei',
        'Asia/Shanghai': 'Asia/Shanghai',
        'Asia/Tokyo': 'Asia/Tokyo',
        'America/New_York': 'America/New_York',
        'America/Los_Angeles': 'America/Los_Angeles',
        'Europe/London': 'Europe/London',
        'Europe/Paris': 'Europe/Paris'
    }
    
    # 常用日期格式
    DATE_FORMATS = {
        'iso': '%Y-%m-%d',
        'iso_datetime': '%Y-%m-%dT%H:%M:%S',
        'iso_full': '%Y-%m-%dT%H:%M:%S.%fZ',
        'human': '%Y年%m月%d日',
        'human_datetime': '%Y年%m月%d日 %H:%M:%S',
        'us': '%m/%d/%Y',
        'us_datetime': '%m/%d/%Y %H:%M:%S',
        'eu': '%d/%m/%Y',
        'eu_datetime': '%d/%m/%Y %H:%M:%S',
        'compact': '%Y%m%d',
        'compact_datetime': '%Y%m%d_%H%M%S',
        'log': '%Y-%m-%d %H:%M:%S'
    }
    
    @staticmethod
    def now(tz: Optional[str] = None) -> datetime:
        """
        獲取當前時間
        
        Args:
            tz: 時區名稱（可選）
            
        Returns:
            datetime: 當前時間
        """
        if tz:
            timezone_obj = pytz.timezone(tz)
            return datetime.now(timezone_obj)
        else:
            return datetime.now(UTC).replace(tzinfo=pytz.UTC)
    
    @staticmethod
    def utc_now() -> datetime:
        """
        獲取當前 UTC 時間
        
        Returns:
            datetime: 當前 UTC 時間
        """
        return datetime.now(UTC).replace(tzinfo=pytz.UTC)
    
    @staticmethod
    def format_datetime(
        dt: datetime,
        format_name: str = 'iso_datetime',
        custom_format: Optional[str] = None
    ) -> str:
        """
        格式化日期時間
        
        Args:
            dt: 日期時間物件
            format_name: 格式名稱
            custom_format: 自定義格式（可選）
            
        Returns:
            str: 格式化後的字符串
        """
        try:
            if custom_format:
                return dt.strftime(custom_format)
            
            format_str = DateTimeUtils.DATE_FORMATS.get(format_name, '%Y-%m-%d %H:%M:%S')
            return dt.strftime(format_str)
        except Exception as e:
            logger.error(f"Error formatting datetime: {e}")
            return str(dt)
    
    @staticmethod
    def parse_datetime(
        date_string: str,
        format_name: Optional[str] = None,
        custom_format: Optional[str] = None
    ) -> datetime:
        """
        解析日期時間字符串
        
        Args:
            date_string: 日期時間字符串
            format_name: 格式名稱（可選）
            custom_format: 自定義格式（可選）
            
        Returns:
            datetime: 解析後的日期時間物件
        """
        try:
            if custom_format:
                return datetime.strptime(date_string, custom_format)
            
            if format_name:
                format_str = DateTimeUtils.DATE_FORMATS.get(format_name)
                if format_str:
                    return datetime.strptime(date_string, format_str)
            
            # 使用 dateutil 進行智能解析
            return parser.parse(date_string)
            
        except Exception as e:
            logger.error(f"Error parsing datetime string '{date_string}': {e}")
            raise DateTimeError(f"無法解析日期時間字符串: {date_string}")
    
    @staticmethod
    def convert_timezone(dt: datetime, target_tz: str) -> datetime:
        """
        轉換時區
        
        Args:
            dt: 日期時間物件
            target_tz: 目標時區
            
        Returns:
            datetime: 轉換時區後的日期時間物件
        """
        try:
            target_timezone = pytz.timezone(target_tz)
            
            # 如果沒有時區資訊，假設為 UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=pytz.UTC)
            
            return dt.astimezone(target_timezone)
            
        except Exception as e:
            logger.error(f"Error converting timezone: {e}")
            raise DateTimeError(f"無法轉換時區: {target_tz}")
    
    @staticmethod
    def time_ago(dt: datetime, now: Optional[datetime] = None) -> str:
        """
        計算時間差並返回人類可讀的字符串
        
        Args:
            dt: 過去的時間
            now: 當前時間（可選）
            
        Returns:
            str: 時間差的描述
        """
        if now is None:
            now = DateTimeUtils.utc_now()
        
        # 確保兩個時間都有時區資訊
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=pytz.UTC)
        
        # 計算時間差
        delta = now - dt
        
        if delta.days > 0:
            if delta.days == 1:
                return "1 天前"
            elif delta.days < 7:
                return f"{delta.days} 天前"
            elif delta.days < 30:
                weeks = delta.days // 7
                return f"{weeks} 週前"
            elif delta.days < 365:
                months = delta.days // 30
                return f"{months} 個月前"
            else:
                years = delta.days // 365
                return f"{years} 年前"
        
        seconds = delta.seconds
        
        if seconds < 60:
            return "剛剛"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} 分鐘前"
        else:
            hours = seconds // 3600
            return f"{hours} 小時前"
    
    @staticmethod
    def add_time(
        dt: datetime,
        years: int = 0,
        months: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0
    ) -> datetime:
        """
        增加時間
        
        Args:
            dt: 基準時間
            years: 年數
            months: 月數
            days: 天數
            hours: 小時數
            minutes: 分鐘數
            seconds: 秒數
            
        Returns:
            datetime: 增加時間後的日期時間物件
        """
        # 使用 relativedelta 處理年月的增加
        if years or months:
            dt = dt + relativedelta(years=years, months=months)
        
        # 使用 timedelta 處理天、小時、分鐘、秒的增加
        if days or hours or minutes or seconds:
            dt = dt + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        
        return dt
    
    @staticmethod
    def subtract_time(
        dt: datetime,
        years: int = 0,
        months: int = 0,
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0
    ) -> datetime:
        """
        減少時間
        
        Args:
            dt: 基準時間
            years: 年數
            months: 月數
            days: 天數
            hours: 小時數
            minutes: 分鐘數
            seconds: 秒數
            
        Returns:
            datetime: 減少時間後的日期時間物件
        """
        # 使用 relativedelta 處理年月的減少
        if years or months:
            dt = dt - relativedelta(years=years, months=months)
        
        # 使用 timedelta 處理天、小時、分鐘、秒的減少
        if days or hours or minutes or seconds:
            dt = dt - timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        
        return dt
    
    @staticmethod
    def get_start_of_day(dt: datetime) -> datetime:
        """
        獲取一天的開始時間
        
        Args:
            dt: 日期時間物件
            
        Returns:
            datetime: 一天的開始時間（00:00:00）
        """
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def get_end_of_day(dt: datetime) -> datetime:
        """
        獲取一天的結束時間
        
        Args:
            dt: 日期時間物件
            
        Returns:
            datetime: 一天的結束時間（23:59:59.999999）
        """
        return dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    @staticmethod
    def get_start_of_week(dt: datetime, week_start: int = 0) -> datetime:
        """
        獲取一週的開始時間
        
        Args:
            dt: 日期時間物件
            week_start: 週的開始日（0=週一，6=週日）
            
        Returns:
            datetime: 一週的開始時間
        """
        days_since_start = (dt.weekday() - week_start) % 7
        start_of_week = dt - timedelta(days=days_since_start)
        return DateTimeUtils.get_start_of_day(start_of_week)
    
    @staticmethod
    def get_end_of_week(dt: datetime, week_start: int = 0) -> datetime:
        """
        獲取一週的結束時間
        
        Args:
            dt: 日期時間物件
            week_start: 週的開始日（0=週一，6=週日）
            
        Returns:
            datetime: 一週的結束時間
        """
        start_of_week = DateTimeUtils.get_start_of_week(dt, week_start)
        end_of_week = start_of_week + timedelta(days=6)
        return DateTimeUtils.get_end_of_day(end_of_week)
    
    @staticmethod
    def get_start_of_month(dt: datetime) -> datetime:
        """
        獲取一個月的開始時間
        
        Args:
            dt: 日期時間物件
            
        Returns:
            datetime: 一個月的開始時間
        """
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def get_end_of_month(dt: datetime) -> datetime:
        """
        獲取一個月的結束時間
        
        Args:
            dt: 日期時間物件
            
        Returns:
            datetime: 一個月的結束時間
        """
        last_day = calendar.monthrange(dt.year, dt.month)[1]
        return dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    
    @staticmethod
    def get_start_of_year(dt: datetime) -> datetime:
        """
        獲取一年的開始時間
        
        Args:
            dt: 日期時間物件
            
        Returns:
            datetime: 一年的開始時間
        """
        return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def get_end_of_year(dt: datetime) -> datetime:
        """
        獲取一年的結束時間
        
        Args:
            dt: 日期時間物件
            
        Returns:
            datetime: 一年的結束時間
        """
        return dt.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
    
    @staticmethod
    def is_weekend(dt: datetime) -> bool:
        """
        判斷是否為週末
        
        Args:
            dt: 日期時間物件
            
        Returns:
            bool: 是否為週末
        """
        return dt.weekday() >= 5  # 週六=5, 週日=6
    
    @staticmethod
    def is_business_day(dt: datetime) -> bool:
        """
        判斷是否為工作日
        
        Args:
            dt: 日期時間物件
            
        Returns:
            bool: 是否為工作日
        """
        return not DateTimeUtils.is_weekend(dt)
    
    @staticmethod
    def get_business_days_count(start_date: datetime, end_date: datetime) -> int:
        """
        計算兩個日期之間的工作日數量
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            
        Returns:
            int: 工作日數量
        """
        count = 0
        current_date = start_date
        
        while current_date <= end_date:
            if DateTimeUtils.is_business_day(current_date):
                count += 1
            current_date += timedelta(days=1)
        
        return count
    
    @staticmethod
    def get_age(birth_date: datetime, reference_date: Optional[datetime] = None) -> int:
        """
        計算年齡
        
        Args:
            birth_date: 出生日期
            reference_date: 參考日期（可選，默認為今天）
            
        Returns:
            int: 年齡
        """
        if reference_date is None:
            reference_date = DateTimeUtils.now()
        
        age = reference_date.year - birth_date.year
        
        # 檢查是否還沒到生日
        if (reference_date.month, reference_date.day) < (birth_date.month, birth_date.day):
            age -= 1
        
        return age
    
    @staticmethod
    def get_quarter(dt: datetime) -> int:
        """
        獲取季度
        
        Args:
            dt: 日期時間物件
            
        Returns:
            int: 季度（1-4）
        """
        return (dt.month - 1) // 3 + 1
    
    @staticmethod
    def get_week_number(dt: datetime) -> int:
        """
        獲取週數
        
        Args:
            dt: 日期時間物件
            
        Returns:
            int: 週數
        """
        return dt.isocalendar()[1]
    
    @staticmethod
    def get_day_of_year(dt: datetime) -> int:
        """
        獲取一年中的第幾天
        
        Args:
            dt: 日期時間物件
            
        Returns:
            int: 一年中的第幾天
        """
        return dt.timetuple().tm_yday
    
    @staticmethod
    def generate_date_range(
        start_date: datetime,
        end_date: datetime,
        step: timedelta = timedelta(days=1)
    ) -> List[datetime]:
        """
        生成日期範圍
        
        Args:
            start_date: 開始日期
            end_date: 結束日期
            step: 步長
            
        Returns:
            List[datetime]: 日期列表
        """
        dates = []
        current_date = start_date
        
        while current_date <= end_date:
            dates.append(current_date)
            current_date += step
        
        return dates
    
    @staticmethod
    def unix_timestamp(dt: datetime) -> int:
        """
        獲取 Unix 時間戳
        
        Args:
            dt: 日期時間物件
            
        Returns:
            int: Unix 時間戳
        """
        return int(dt.timestamp())
    
    @staticmethod
    def from_unix_timestamp(timestamp: Union[int, float], tz: Optional[str] = None) -> datetime:
        """
        從 Unix 時間戳創建日期時間物件
        
        Args:
            timestamp: Unix 時間戳
            tz: 時區（可選）
            
        Returns:
            datetime: 日期時間物件
        """
        dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        
        if tz:
            target_tz = pytz.timezone(tz)
            dt = dt.astimezone(target_tz)
        
        return dt
    
    @staticmethod
    def is_leap_year(year: int) -> bool:
        """
        判斷是否為閏年
        
        Args:
            year: 年份
            
        Returns:
            bool: 是否為閏年
        """
        return calendar.isleap(year)


# 便捷函數
def now(tz: Optional[str] = None) -> datetime:
    """獲取當前時間"""
    return DateTimeUtils.now(tz)


def utc_now() -> datetime:
    """獲取當前 UTC 時間"""
    return DateTimeUtils.utc_now()


def format_datetime(dt: datetime, format_name: str = 'log', format_str: Optional[str] = None) -> str:
    """格式化日期時間"""
    if format_str:
        return dt.strftime(format_str)
    return DateTimeUtils.format_datetime(dt, format_name)


def parse_datetime(date_string: str, format_str: Optional[str] = None) -> datetime:
    """解析日期時間字符串"""
    if format_str:
        return datetime.strptime(date_string, format_str)
    return DateTimeUtils.parse_datetime(date_string)


def time_ago(dt: datetime) -> str:
    """計算時間差"""
    return DateTimeUtils.time_ago(dt)


def convert_timezone(dt: datetime, target_tz: str) -> datetime:
    """轉換時區"""
    return DateTimeUtils.convert_timezone(dt, target_tz)


def get_start_of_day(dt: datetime) -> datetime:
    """獲取一天的開始時間"""
    return DateTimeUtils.get_start_of_day(dt)


def get_end_of_day(dt: datetime) -> datetime:
    """獲取一天的結束時間"""
    return DateTimeUtils.get_end_of_day(dt)


def is_business_day(dt: datetime, holidays: Optional[List] = None) -> bool:
    """檢查是否為工作日"""
    # 先檢查是否為週末
    if not DateTimeUtils.is_business_day(dt):
        return False
    
    # 如果提供了假期列表，檢查是否為假期
    if holidays:
        date_obj = dt.date() if hasattr(dt, 'date') else dt
        return date_obj not in holidays
    
    return True


def get_business_days_count(start_date: datetime, end_date: datetime) -> int:
    """計算兩個日期之間的工作日數量"""
    return DateTimeUtils.get_business_days_count(start_date, end_date)


def add_business_days(start_date: datetime, days: int) -> datetime:
    """添加工作日（簡化實現）"""
    if days == 0:
        return start_date
    
    current = start_date
    remaining = abs(days)
    direction = 1 if days > 0 else -1
    
    while remaining > 0:
        current += timedelta(days=direction)
        if is_business_day(current):
            remaining -= 1
    
    return current


def get_business_days_between(start_date: datetime, end_date: datetime) -> int:
    """獲取兩個日期之間的工作日數量（別名）"""
    return get_business_days_count(start_date, end_date)


def format_duration(duration: timedelta) -> str:
    """格式化時間間隔（簡化實現）"""
    total_seconds = int(duration.total_seconds())
    
    if total_seconds < 0:
        return f"-{format_duration(-duration)}"
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小時")
    if minutes > 0:
        parts.append(f"{minutes}分鐘")
    if seconds > 0 or not parts:
        parts.append(f"{seconds}秒")
    
    return "".join(parts)


def parse_duration(duration_str: str) -> timedelta:
    """解析時間間隔字符串（簡化實現）"""
    import re
    
    # 簡化的正則表達式匹配
    patterns = {
        r'(\d+)天': lambda m: timedelta(days=int(m.group(1))),
        r'(\d+)小時': lambda m: timedelta(hours=int(m.group(1))),
        r'(\d+)分鐘': lambda m: timedelta(minutes=int(m.group(1))),
        r'(\d+)秒': lambda m: timedelta(seconds=int(m.group(1)))
    }
    
    total_delta = timedelta()
    matched = False
    
    for pattern, converter in patterns.items():
        matches = re.finditer(pattern, duration_str)
        for match in matches:
            total_delta += converter(match)
            matched = True
    
    if not matched:
        raise DateTimeError(f"無法解析時間間隔: {duration_str}")
    
    return total_delta


def get_time_ranges(start: datetime, end: datetime, interval: str) -> List[Tuple[datetime, datetime]]:
    """獲取時間範圍列表（簡化實現）"""
    if start >= end:
        raise DateTimeError("開始時間必須早於結束時間")
    
    ranges = []
    current = start
    
    if interval == "daily":
        current_date = start.date()
        end_date = end.date()
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=start.tzinfo)
            day_end = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=start.tzinfo)
            ranges.append((day_start, day_end))
            current_date += timedelta(days=1)
    elif interval == "weekly":
        while current <= end:
            next_week = current + timedelta(weeks=1)
            if current < end:
                ranges.append((current, min(next_week, end)))
            elif current == end:
                # 如果剛好在結束點，添加一個短範圍
                ranges.append((current, end))
                break
            current = next_week
    elif interval == "monthly":
        while current < end:
            # 簡化的月份加法
            if current.month == 12:
                next_month = current.replace(year=current.year + 1, month=1)
            else:
                next_month = current.replace(month=current.month + 1)
            ranges.append((current, min(next_month, end)))
            current = next_month
    else:
        raise DateTimeError(f"不支援的間隔類型: {interval}")
    
    return ranges
"""自定义异常类"""


class SimuEmperorError(Exception):
    """基础异常类"""

    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


class FileOperationError(SimuEmperorError):
    """文件操作异常"""


class JSONParseError(SimuEmperorError):
    """JSON 解析异常"""


class DataValidationError(SimuEmperorError):
    """数据验证异常"""

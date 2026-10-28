"""备份适配器与界面共用的既有异常类型；不包含恢复算法。"""


class BackupValidationError(ValueError):
    pass


class RestoreSafetyError(BackupValidationError):
    """恢复安全条件不满足或切换后失败；消息保留后端实际保护/回滚状态。"""

class BusinessRuleApiError(Exception):
    """
    業務ルール違反を固定形式のAPIエラーレスポンスに変換するための例外。
    """

    status_code = 400

    def __init__(self, *, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

    def to_response_data(self):
        return {
            "code": self.code,
            "message": self.message,
            "status_code": self.status_code,
        }

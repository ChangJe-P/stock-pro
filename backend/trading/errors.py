"""도메인 서비스가 HTTP 상태로 변환될 안전한 오류를 던질 때 쓰는 예외.

메시지(detail)에는 비밀값·연결 문자열·환경변수 값 전체를 넣지 않는다.
"""


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail

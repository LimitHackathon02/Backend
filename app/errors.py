#에러모양 통일
"""모든 에러를 {"detail": {"code": ..., "message": ...}} 한 가지 모양으로 통일."""
from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail={"code": code, "message": message})
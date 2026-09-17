from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = "La operación entra en conflicto con el estado actual."
    default_code = "conflict"


class UnprocessableEntity(APIException):
    status_code = 422
    default_detail = "El contenido no pudo validarse."
    default_code = "unprocessable_entity"


def _first_error_code(value):
    if hasattr(value, "code"):
        return value.code
    if isinstance(value, dict):
        for nested in value.values():
            code = _first_error_code(nested)
            if code:
                return code
    if isinstance(value, (list, tuple)):
        for nested in value:
            code = _first_error_code(nested)
            if code:
                return code
    return None


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    code = getattr(exc, "default_code", "api_error")
    message = "La solicitud no pudo procesarse."

    if isinstance(detail, dict) and "detail" in detail:
        value = detail["detail"]
        message = str(value)
        if hasattr(value, "code"):
            code = value.code
        details = {}
    else:
        details = detail
        code = _first_error_code(detail) or code

    response.data = {
        "error": {
            "code": str(code).upper(),
            "message": message,
            "details": details,
        }
    }
    return response

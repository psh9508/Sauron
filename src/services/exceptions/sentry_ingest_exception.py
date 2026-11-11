from src.services.exceptions.app_base_error import AppBaseError


class SentryAuthMissingError(AppBaseError):
    status_code = 401
    code = "SentryAuthMissingError"
    message = "Missing sentry_key in X-Sentry-Auth header, query string, or envelope DSN"


class InvalidSentryEnvelopeError(AppBaseError):
    status_code = 400
    code = "InvalidSentryEnvelopeError"
    message = "Malformed Sentry envelope"


class UnsupportedContentEncodingError(AppBaseError):
    status_code = 415
    code = "UnsupportedContentEncodingError"
    message = "Unsupported Content-Encoding (supported: gzip, deflate, br)"


class SentryEnvelopeTooLargeError(AppBaseError):
    status_code = 413
    code = "SentryEnvelopeTooLargeError"
    message = "Sentry envelope exceeds the maximum allowed size"

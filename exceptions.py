class IncorrectResponseException(TypeError):
    """В ответе не обнаружены ожидаемые ключи."""

    pass


class UnknownStatusException(KeyError):
    """В ответе не обнаружены ожидаемые ключи."""

    pass


class HomeworkMissingException(Exception):
    """В ответе API домашки нет ключа `homework_name`."""

    pass


class ResponseJsonError(Exception):
    """Ошибка формата ответа API"""

    def __init__(self, message='Ответ API не в формате JSON'):
        self.message = message
        super().__init__(self.message)

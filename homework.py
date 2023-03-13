import logging
import os
import time
from http import HTTPStatus
from logging import StreamHandler
from sys import stdout

import requests
import telegram
from dotenv import load_dotenv
from requests import HTTPError

from exceptions import (HomeworkMissingException, IncorrectResponseException,
                        UnknownStatusException, ResponseJsonError)

load_dotenv()

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD: int = 60 * 10
ERROR_CACHE_LIFETIME: int = 60 * 60 * 24

HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение "{message}" отправлено')
    except Exception as error:
        error_message = f'При отправке сообщения произошла ошибка: {error}'
        logger.exception(error_message)


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as i:
        raise Exception(f'{ENDPOINT} не передает данные: {i}')
    if response.status_code != HTTPStatus.OK:
        raise HTTPError(
            f'Ответ от сервера не соответствует ожиданию:'
            f'{response.status_code}'
        )
    try:
        response_json = response.json()
        logger.info('Ответ API получен')
        return response_json
    except Exception:
        raise ResponseJsonError


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise IncorrectResponseException('response не является словарем')
    homeworks = response.get('homeworks')
    if 'homeworks' not in response:
        raise IncorrectResponseException('Нет ключа "homeworks" в response')
    if 'current_date' not in response:
        raise IncorrectResponseException('Нет ключа "current_date" в response')
    if not isinstance(homeworks, list):
        raise IncorrectResponseException('"homeworks" не является списком')
    return homeworks


def parse_status(homework):
    """Отправляет статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is None:
        raise HomeworkMissingException(
            f'`homework_name` отсутствует: {homework_name}')
    if homework_status not in HOMEWORK_VERDICTS:
        error_message = (
            f'Получен неизвестный статус работы: {homework_status}')
        raise UnknownStatusException(error_message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    params = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    available = all(params)
    return available


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют обязательные переменные окружения')
        raise SystemExit('Ошибка, бот остановлен!')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time()) - RETRY_PERIOD
    last_message_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            else:
                logger.debug('Нет новых статусов')
            current_timestamp = response.get(
                'current_data', int(time.time())
            )
        except Exception as error:
            message = f'Что-то сломалось при отправке, {error}'
            logger.error(message)
            if message != last_message_error:
                send_message(bot, message)
                last_message_error = message
        else:
            last_message_error = ''
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

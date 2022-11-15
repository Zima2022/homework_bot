import logging
import os
import sys
import time
import requests
import telegram

from dotenv import load_dotenv
from http import HTTPStatus
from requests import HTTPError
from telegram import TelegramError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """
    Отправляет сообщение в Telegram чат.
    Принимает на вход два параметра:
        экземпляр класса Bot и строку с текстом сообщения.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except TelegramError as error:
        logger.error(
            f'Бот не смог отправить сообщение {message}. Ошибка {error}'
        )
    else:
        logger.info(f'Бот отправил сообщение "{message}"')


def get_api_answer(current_timestamp: int) -> dict:
    """
    Делает запрос к эндпоинту API-сервиса.
    В случае успешного запроса вернет ответ API в виде словаря.
    Принимает на вход один параметр:
        время в формате Unix time
    """
    timestamp = current_timestamp or int(time.time())
    request_params = {
        'url': ENDPOINT,
        'headers': {'Authorization': f'OAuth {PRACTICUM_TOKEN}'},
        'params': {'from_date': timestamp},
    }
    response = requests.get(**request_params)

    if response.status_code != HTTPStatus.OK:
        message = f'Код ответа API: {response.status_code}'
        logger.error(message)
        raise HTTPError(message)

    if not response:
        message = 'Получен пусто ответ при обращении к API'
        logger.error(message)
        raise Exception(message)

    return response.json()


def check_response(response: dict) -> list:
    """
    Проверяет ответ API на корректность.
    Вернет список домашних работ, если он есть в ответе API.
    Принимает на вход один параметр:
        ответ API в виде словаря.
    """
    if not response:
        message = 'Получен пустой ответ при обращении к API'
        logger.error(message)
        raise Exception(message)

    if not isinstance(response, dict):
        message = 'Получен некорретный ответ при обрщаении к API'
        logger.error(message)
        raise TypeError(message)

    for key in ['homeworks', 'current_date']:
        if key not in response:
            message = f'Отсутствует ключ "{key}" в ответе API'
            logger.error(message)
            raise KeyError(message)

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        message = 'Объект по ключу "homeworks" не является списком'
        logger.error(message)
        raise TypeError(message)

    return homeworks


def parse_status(homework: list) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    Принимает на вход один параметр:
        домашнюю работу в виде словаря.
    """
    for key in ['homework_name', 'status']:
        if key not in homework:
            message = f'Отсутствует ключ "{key}" в объекте "homework"'
            logger.error(message)
            raise KeyError(message)

    if not homework['homework_name']:
        message = 'Отсуствует имя проекта'
        logger.error(message)
    else:
        homework_name = homework['homework_name']

    if homework['status'] not in HOMEWORK_STATUSES:
        message = 'Неизвестный статус проекта'
        logger.error(message)
    else:
        homework_status = homework['status']
        verdict = HOMEWORK_STATUSES.get(homework_status)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """
    Проверяет доступность переменных окружения.
    Вернет False, если отсутствует хотя бы одна переменная окружения,
    Иначе вернет True.
    """
    result = all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])
    if not result:
        logger.critical(f"Отсутствует обязательная переменная окружения")

    return result


def main() -> None:
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            if not check_tokens():
                sys.exit()
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                status = homework[0]['status']
            else:
                status = None
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            current_timestamp = int(time.time())
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                new_status = homework[0]['status']
            else:
                new_status = None

            if new_status and status != new_status:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                message = 'Статус работы не изменился'
                logger.debug(message)


if __name__ == '__main__':
    main()

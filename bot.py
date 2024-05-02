import telebot
from telebot import types
from config import *
import gpt
import logging
import database as db
import speechkit as sk
import math


logging.basicConfig(filename="logs.txt", encoding="utf-8", level=logging.DEBUG, filemode="w",
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)


def add_buttons(buttons):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    keyboard.add(*buttons)
    return keyboard


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id,
                     f"Привет, {message.from_user.first_name}. Отправь голосовое сообщение с вопросом, и YaGPT ответит на него."
                     "Напиши /ask_gpt, чтобы начать А когда ты закончишь, напиши /end.",
                     reply_markup=add_buttons(("/new_story",)))


@bot.message_handler(commands=["debug"])
def debug(message):
    with open("logs.txt", "rb") as logs:
        bot.send_document(message.chat.id, logs)


@bot.message_handler(commands=['tts'])
def tts_check(message):
    chat_id = message.chat.id
    db.insert_user_to_db(chat_id)

    if db.get_data_from_db(chat_id=chat_id, columns="used_tts_tokens")[0][0] >= USER_TTS_TOKEN_LIMIT:
        bot.send_message(chat_id, 'Кончились токены')
        return

    bot.send_message(chat_id, 'Введите текст для озвучки')
    bot.register_next_step_handler(message, send_tts)
    return


def send_tts(message):
    chat_id = message.chat.id

    if message.content_type != 'text':
        bot.send_message(chat_id, 'Введите текст')
        bot.register_next_step_handler(message, send_tts)
        return

    curr_tts_tokens = int(db.get_data_from_db(chat_id=chat_id, columns="used_tts_tokens")[0][0])

    if len(message.text) + curr_tts_tokens < USER_TTS_TOKEN_LIMIT:
        speech = sk.text_to_speech(message.text)

        if speech:
            bot.send_voice(chat_id, speech)
            db.update_db(chat_id=chat_id, columns=("used_tts_tokens",), values=(curr_tts_tokens + len(message.text),))
        else:
            bot.send_message(chat_id, "Ошибка при запросе к SpeechKit")

    else:
        bot.send_message(chat_id, "Слишком большой текст.")
        return


@bot.message_handler(commands=['stt'])
def tts_check(message):
    chat_id = message.chat.id
    db.insert_user_to_db(chat_id)

    if int(db.get_data_from_db(chat_id, "used_stt_blocks")[0][0]) >= USER_STT_BLOCKS_LIMIT:
        bot.send_message(chat_id, 'Кончились токены')
        return

    bot.send_message(chat_id, 'Отправьте голосовое сообщение')
    bot.register_next_step_handler(message, send_stt)
    return


def send_stt(message):
    chat_id = message.chat.id

    if not message.voice:
        bot.send_message(chat_id, 'Отправьте голосовое сообщение')
        bot.register_next_step_handler(message, send_stt)
        return

    if message.voice.duration >= 30:
        bot.send_message(chat_id, 'Отправьте голосовое сообщение короче 30 секунд')
        bot.register_next_step_handler(message, send_stt)
        return

    curr_stt_blocks = int(db.get_data_from_db(chat_id=chat_id, columns="used_stt_blocks")[0][0])
    if curr_stt_blocks < USER_STT_BLOCKS_LIMIT:
        db.update_db(chat_id=chat_id, columns=("used_stt_blocks",), values=(curr_stt_blocks + math.ceil(message.voice.duration / 15),))
        file_info = bot.get_file(message.voice.file_id)
        file = bot.download_file(file_info.file_path)
        bot.send_message(chat_id, sk.speech_to_text(file))

    else:
        bot.send_message(chat_id, 'Закончились токены')
        bot.register_next_step_handler(message, send_stt)
        return


@bot.message_handler(content_types=["voice"])
def voice_gpt_handler(message):
    db.insert_user_to_db(message.chat.id)
  
    curr_gpt_tokens = int(db.get_data_from_db(message.chat.id, "used_gpt_tokens")[0][0])
    curr_stt_blocks = int(db.get_data_from_db(message.chat.id, "used_stt_blocks")[0][0])
    curr_tts_tokens = int(db.get_data_from_db(message.chat.id, "used_tts_tokens")[0][0])

    used_stt_blocks = math.ceil(message.voice.duration / 15)
    if curr_stt_blocks + used_stt_blocks < USER_STT_BLOCKS_LIMIT:
        db.update_db(message.chat.id, columns=("used_stt_blocks",), values=(curr_stt_blocks + used_stt_blocks,))
        text = sk.speech_to_text(bot.download_file(bot.get_file(message.voice.file_id).file_path))

        if curr_gpt_tokens < USER_GPT_TOKEN_LIMIT:
            answer, used_gpt_tokens = gpt.get_answer(text)
            db.update_db(message.chat.id, columns=("used_gpt_tokens",), values=(curr_gpt_tokens + used_gpt_tokens,))

            if curr_tts_tokens + len(answer) < USER_TTS_TOKEN_LIMIT:
                speech = sk.text_to_speech(answer)
                bot.send_voice(message.chat.id, speech)
            else:
                bot.send_message(message.chat.id, answer)

        else:
            bot.send_message(message.chat.id, "Вы исчерпали свой лимит GPT токенов")

    else:
        bot.send_message(message.chat.id, "Вы исчерпали свой лимит STT токенов")


@bot.message_handler(content_types=["text"])
def text_gpt_handler(message):
    db.insert_user_to_db(message.chat.id)
  
    curr_tokens = int(db.get_data_from_db(message.chat.id, "used_gpt_tokens")[0][0])

    if curr_tokens < USER_GPT_TOKEN_LIMIT:
        answer, used_tokens = gpt.get_answer(message.text)

        bot.send_message(message.chat.id, answer, reply_markup=add_buttons(("/end",)))
        db.update_db(message.chat.id, columns=("used_gpt_tokens",), values=(curr_tokens + used_tokens,))

    else:

        bot.send_message(message.chat.id, "Вы исчерпали свой лимит токенов для GPT",)


if __name__ == "__main__":
    bot.infinity_polling()
    logging.info("Бот запущен")

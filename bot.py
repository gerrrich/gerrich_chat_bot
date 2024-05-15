import logging
import os

import telebot
from langchain.chains import LLMChain
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.messages import SystemMessage
from langchain.chains.conversation.memory import ConversationBufferWindowMemory
from langchain_groq import ChatGroq
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonCommands, BotCommand

if os.environ.get('USER', os.environ.get('USERNAME')) == 'gerrich':
    IS_DEBUG = True
    telegram_bot_api_key = '7040062489:AAEeZR-Wam-xh8yUQ1CE06OJconoQObvYxY'
else:
    IS_DEBUG = False
    telegram_bot_api_key = '7072266877:AAEzRwuHbELQ_EeiGIku4n9MBdcui_9b3lQ'

groq_api_key = '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'

models = ['llama3-8b-8192', 'llama3-70b-8192', 'mixtral-8x7b-32768', 'gemma-7b-it']

default_context_length = 3
default_model = models[0]

bot_default_role = 'полезный, уважительный и честный помощник'
system_message = (f"Я всегда отвечаю на русском языке. Я {bot_default_role}. "
                  f"Если вопрос не имеет никакого смысла или мне не понятен, я объясняю, почему, "
                  f"вместо того, чтобы попытаться ответить на такой вопрос. "
                  f"Если я не знаю ответ на вопрос, я не даю ложную информацию, "
                  f"никогда не вру и честно признаюсь, что не знаю ответа.")
users = {}

bot = telebot.TeleBot(telegram_bot_api_key)

logging.basicConfig(level=logging.INFO)

model_markup_text = 'Выберите модель:'
model_markup = InlineKeyboardMarkup([[InlineKeyboardButton(models[0], callback_data=models[0])],
                                     [InlineKeyboardButton(models[1], callback_data=models[1])],
                                     [InlineKeyboardButton(models[2], callback_data=models[2])],
                                     [InlineKeyboardButton(models[3], callback_data=models[3])]])

context_markup_text = 'Установите контекст (количество последних сообщений):'
context_markup = InlineKeyboardMarkup([[InlineKeyboardButton('1', callback_data='1'),
                                        InlineKeyboardButton('2', callback_data='2'),
                                        InlineKeyboardButton('3', callback_data='3')],
                                       [InlineKeyboardButton('5', callback_data='5'),
                                        InlineKeyboardButton('7', callback_data='7'),
                                        InlineKeyboardButton('10', callback_data='10')]])

reset_markup_text = 'Сбросить контекст'
reset_markup = InlineKeyboardMarkup([[InlineKeyboardButton('Сбросить', callback_data='yes'),
                                      InlineKeyboardButton('Отмена', callback_data='no')]])

bot.set_my_commands([
    BotCommand(command='start', description='Начать'),
    BotCommand(command='model', description='Выбрать модель'),
    BotCommand(command='context', description='Установить контекст'),
    BotCommand(command='reset', description='Сбросить контекст')
])


@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id not in users:
        users[message.from_user.id] = {'chat_history': [], 'model': default_model, 'memory_length': default_context_length}

    bot.set_chat_menu_button(message.chat.id, MenuButtonCommands('commands'))

    bot.send_message(message.from_user.id, f"Привет! Я ваш дружелюбный чат-бот gerrich. "
                                           f"Я могу помочь ответить на ваши вопросы, "
                                           f"предоставить информацию или просто пообщаться. "
                                           f"Я также очень шустрый! Давайте начнем наш разговор! "
                                           f"Модель по умолчанию - \"{default_model}\", "
                                           f"контекст - 3 последних сообщения.")


@bot.message_handler(commands=['context'])
def set_context(message):
    if message.from_user.id not in users:
        users[message.from_user.id] = {'chat_history': [], 'model': default_model, 'memory_length': default_context_length}

    bot.send_message(message.from_user.id, context_markup_text, reply_markup=context_markup)


@bot.message_handler(commands=['model'])
def set_model(message):
    if message.from_user.id not in users:
        users[message.from_user.id] = {'chat_history': [], 'model': default_model, 'memory_length': default_context_length}

    bot.send_message(message.from_user.id, model_markup_text, reply_markup=model_markup)


@bot.message_handler(commands=['reset'])
def reset(message):
    if message.from_user.id not in users:
        users[message.from_user.id] = {'chat_history': [], 'model': default_model, 'memory_length': default_context_length}

    bot.send_message(message.from_user.id, reset_markup_text, reply_markup=reset_markup)


@bot.callback_query_handler(func=lambda call: True)
def callback_set_model(call):
    if call.message.text == model_markup_text:
        users[call.from_user.id]['model'] = call.data
        bot.answer_callback_query(call.id, f"Выбрана модель - {call.data}", show_alert=True)

    elif call.message.text == context_markup_text:
        users[call.from_user.id]['memory_length'] = int(call.data)
        bot.answer_callback_query(call.id, f"Контекст - {call.data}", show_alert=True)

    elif call.message.text == reset_markup_text:
        if call.data == 'yes':
            users[call.from_user.id]['chat_history'] = []
            bot.answer_callback_query(call.id, f"Контекст очищен", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"Отмена")

    bot.delete_message(call.from_user.id, call.message.message_id)
    bot.delete_message(call.from_user.id, call.message.message_id - 1)


@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    user_question = message.text
    chat_id = message.from_user.id

    # session state variable
    if chat_id not in users:  # new user
        memory = ConversationBufferWindowMemory(k=default_context_length, memory_key="chat_history",
                                                return_messages=True)

        users[chat_id] = {'chat_history': [], 'model': default_model, 'memory_length': default_context_length}
    else:
        memory = ConversationBufferWindowMemory(k=users[chat_id]['memory_length'], memory_key="chat_history",
                                                return_messages=True)

        if len(users[chat_id]['chat_history']) > users[chat_id]['memory_length']:
            users[chat_id]['chat_history'] = users[chat_id]['chat_history'][-users[chat_id]['memory_length']:]

        for message in users[chat_id]['chat_history']:
            memory.save_context(
                {'input': message['human']},
                {'output': message['AI']}
            )

    groq_chat = ChatGroq(
        groq_api_key=groq_api_key,
        model_name=users[chat_id]['model']
    )

    # Construct a chat prompt template using various components
    prompt = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content=system_message
            ),
            MessagesPlaceholder(
                variable_name="chat_history"
            ),
            HumanMessagePromptTemplate.from_template(
                "{human_input}"
            ),
        ]
    )

    # Create a conversation chain using the LangChain LLM (Language Learning Model)
    conversation = LLMChain(
        llm=groq_chat,
        prompt=prompt,
        verbose=True,
        memory=memory,
    )

    # The chatbot's answer is generated by sending the full prompt to the Groq API.
    response = conversation.predict(human_input=user_question)
    message = {'human': user_question, 'AI': response}
    users[chat_id]['chat_history'].append(message)

    bot.send_message(chat_id, response)


while True:
    bot.polling(none_stop=True, interval=0, timeout=0)

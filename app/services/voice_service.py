import os
import json
import tempfile
from openai import OpenAI

# Инициализируем клиента OpenAI (ключ должен быть в .env как OPENAI_API_KEY)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def process_voice_message(audio_bytes: bytes) -> dict:
    """
    1. Переводит аудио в текст (Whisper).
    2. Извлекает из текста сущности (LLM).
    Возвращает словарь: {'category': '...', 'address': '...', 'description': '...'}
    """

    # Telegram присылает файлы в формате OGG (кодек Opus).
    # OpenAI API требует, чтобы у файла было правильное расширение, поэтому используем tempfile.
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_audio:
        temp_audio.write(audio_bytes)
        temp_audio_path = temp_audio.name

    try:
        # ШАГ 1: Speech-to-Text (Whisper)
        with open(temp_audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ru"  # Принудительно ставим русский для скорости
            )

        text = transcript.text
        if not text:
            return {"error": "Не удалось распознать текст"}

        # ШАГ 2: LLM извлекает сущности и отдает строгий JSON
        system_prompt = """
        Ты — ИИ-диспетчер экстренной службы. Проанализируй текст инцидента.
        Твоя задача — вернуть СТРОГИЙ JSON без markdown разметки.
        Поля:
        - category: одна из [Пожар, ДТП, Инфраструктура, Другое]
        - address: извлеченный адрес или null, если не указан
        - description: краткое, четкое описание инцидента (максимум 2 предложения)
        """

        completion = client.chat.completions.create(
            model="gpt-4o-mini",  # Быстрая и дешевая модель
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Текст: {text}"}
            ],
            response_format={"type": "json_object"}  # Гарантирует, что вернется JSON
        )

        response_content = completion.choices[0].message.content
        return json.loads(response_content)

    except Exception as e:
        print(f"Ошибка в voice_service: {e}")
        return {"error": str(e)}

    finally:
        # Обязательно удаляем временный файл
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
<!-- ![](data/Logo.jpg) -->

# 📖 Table of Contents

- [Установка](#установка)
- [Туториалы](#туториалы)
- [llama.cpp](#llamacpp)
- [Датасет](#датасет)
- [Результаты](#результаты)
- [Обучение (lora tuning)](#обучение-lora-tuning)
- [API](#api)

---

## Установка

Перед запуском необходимо собрать фронтенд по адресу [github.com/xpatronum/jaiui](https://github.com/xpatronum/jaiui):

1. `npm ci`
2. `npm run build`
3. Полученные артефакты (js/css/html) положить в папку `jaiai/building`

После этого выполните установку зависимостей:

```bash
pip install -r requirements.txt
```

Мы протестировали и можем уверенно сказать, что на python >= 3.12 всё будет работать точно.

---

## Туториалы

- **Кластеризация:** [notebook/note-clustering.ipynb](notebook/note-clustering.ipynb)
- **LLM pipeline:** [notebook/note-llm-calls.ipynb](notebook/note-llm-calls.ipynb)

---

## llama.cpp

Для inference подразумевается, что [llama.cpp](https://github.com/ggerganov/llama.cpp) уже запущена и доступна для взаимодействия.

---

## Датасет

Тестовый датасет расположен прямо в репозитории и содержит 100 реальных отзывов с нашей разметкой. Используйте его для дебага, запуска и отладки.

**Для получения настоящих датасетов обращайтесь:**

- Telegram: [@itarlinskiy](https://t.me/itarlinskiy)
- Email: <itarlinskiy@yandex.ru>

---

## Результаты

---

## Обучение (lora tuning)

Для понимания подхода к LoRA рекомендуем ознакомиться с [этой статьёй](https://huggingface.co/blog/lora). Мы использовали синтетические данные для дообучения на отзывах, и наши результаты видны ниже (сравнение между gpt-3.5, llama-3.1 8b (наша модель), gpt-4o-mini):

![](data/eval_stats.jpg)

Для дообучения мы использовали как внутренние датасеты (их мы не можем разглашать), так и синтетические, используя следующие параметры:

<TODO>
placeholder

---

## API

<TODO>
placeholder
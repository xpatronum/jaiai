#!/bin/bash

# Скрипт для параллельного запуска scrapy спайдеров в фоне
# Использование: ./run_parallel_scrapers.sh

# Переходим в корневую директорию проекта (где находится scrapy.cfg)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🚀 Запускаем scrapy спайдеры в фоне..."
echo "📁 Рабочая директория: $(pwd)"

# Проверяем, активировано ли виртуальное окружение
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Виртуальное окружение активно: $VIRTUAL_ENV"
    PYTHON_CMD="python"
else
    echo "⚠️  Виртуальное окружение не активно, пытаемся найти myenv..."
    # Ищем виртуальное окружение
    if [ -f "myenv/bin/activate" ]; then
        echo "🔄 Активируем виртуальное окружение myenv"
        source myenv/bin/activate
        PYTHON_CMD="python"
    elif [ -f "../myenv/bin/activate" ]; then
        echo "🔄 Активируем виртуальное окружение ../myenv"
        source ../myenv/bin/activate
        PYTHON_CMD="python"
    else
        echo "❌ Виртуальное окружение не найдено, используем системный Python"
        PYTHON_CMD="python3"
    fi
fi

# Проверяем наличие scrapy команды и получаем полный путь
SCRAPY_PATH=$(command -v scrapy 2>/dev/null)
if [ -z "$SCRAPY_PATH" ]; then
    echo "❌ ОШИБКА: Команда scrapy не найдена!"
    echo "💡 Убедитесь что виртуальное окружение активировано и scrapy установлен"
    echo "💡 Или установите: pip install scrapy"
    echo ""
    echo "🔍 Отладочная информация:"
    echo "PATH: $PATH"
    echo "VIRTUAL_ENV: $VIRTUAL_ENV"
    echo "Python: $(which python)"
    exit 1
fi

echo "✅ Scrapy найден: $SCRAPY_PATH"
echo "✅ Версия: $(scrapy version)"
echo "🔍 Текущий PATH: $PATH"
echo "🔍 Виртуальное окружение: $VIRTUAL_ENV"

# Создаем директорию для логов если её нет
mkdir -p logs

# Функция для запуска спайдера с логированием
run_spider() {
    local spider_name=$1
    local count=$2
    local output_file=$3
    local log_file=$4
    
    echo "📊 Запускаем $spider_name (лимит: $count отзывов)"
    
    # Логируем команду которая будет выполнена
    local full_command="$SCRAPY_PATH crawl $spider_name -a count=$count -o $output_file"
    echo "🔧 Команда: $full_command"
    echo "🔧 Лог файл: logs/$log_file"
    echo "🔧 PATH для nohup: $PATH"
    
    # Записываем отладочную информацию в начало лог файла
    {
        echo "=== SCRAPY SPIDER LOG: $spider_name ==="
        echo "Время запуска: $(date)"
        echo "Команда: $full_command"
        echo "PATH: $PATH"
        echo "VIRTUAL_ENV: $VIRTUAL_ENV"
        echo "Рабочая директория: $(pwd)"
        echo "================================="
        echo ""
    } > "logs/$log_file"
    
    # Способ 1: Используем полный путь к scrapy и явно передаем окружение
    nohup env PATH="$PATH" VIRTUAL_ENV="$VIRTUAL_ENV" "$SCRAPY_PATH" crawl "$spider_name" -a count="$count" -o "$output_file" \
        >> "logs/$log_file" 2>&1 &
    
    local pid=$!
    echo "✅ $spider_name запущен с PID: $pid"
    echo "$pid" > "logs/${spider_name}.pid"
    
    # Даем немного времени на старт и проверяем, что процесс запустился
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        echo "✅ Процесс $spider_name (PID: $pid) успешно запущен"
    else
        echo "❌ ОШИБКА: Процесс $spider_name (PID: $pid) не запустился!"
        echo "📋 Последние строки лога:"
        tail -5 "logs/$log_file" | sed 's/^/    /'
    fi
}

# Запускаем спайдеры
run_spider "banki_all_pages" "4000" "banki.json" "banki_scraper.log"
run_spider "sravni_all_gazprombank_pages" "4000" "sravni.json" "sravni_scraper.log"

echo ""
echo "🎯 Оба спайдера запущены в фоне!"
echo "📁 Результаты будут сохранены в:"
echo "   - banki.json (лимит: 4000 отзывов)"
echo "   - sravni.json (лимит: 4000 отзывов)"
echo ""
echo "📋 Логи доступны в:"
echo "   - logs/banki_scraper.log"
echo "   - logs/sravni_scraper.log"
echo ""
echo "🔍 Проверить статус процессов:"
echo "   ps aux | grep scrapy"
echo "   jobs"
echo ""
echo "📖 Посмотреть логи в реальном времени:"
echo "   tail -f logs/banki_scraper.log"
echo "   tail -f logs/sravni_scraper.log"
echo ""
echo "🛑 Остановить процессы:"
echo "   kill \$(cat logs/banki_all_pages.pid)"
echo "   kill \$(cat logs/sravni_all_gazprombank_pages.pid)"
echo ""
echo "✨ Можете безопасно выйти из SSH сессии - процессы продолжат работу!"
echo ""
echo "🔧 АЛЬТЕРНАТИВНЫЙ СПОСОБ ЗАПУСКА (если что-то пошло не так):"
echo "   nohup bash -c 'source myenv/bin/activate && scrapy crawl banki_all_pages -a count=4000 -o banki.json' > logs/banki_alt.log 2>&1 &"
echo "   nohup bash -c 'source myenv/bin/activate && scrapy crawl sravni_all_gazprombank_pages -a count=4000 -o sravni.json' > logs/sravni_alt.log 2>&1 &"

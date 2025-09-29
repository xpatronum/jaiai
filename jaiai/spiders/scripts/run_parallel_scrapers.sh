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

# Проверяем наличие scrapy
if ! $PYTHON_CMD -c "import scrapy" 2>/dev/null; then
    echo "❌ ОШИБКА: Scrapy не установлен!"
    echo "💡 Установите: pip install scrapy"
    exit 1
fi

echo "✅ Scrapy найден: $($PYTHON_CMD -c 'import scrapy; print(scrapy.__version__)')"

# Создаем директорию для логов если её нет
mkdir -p logs

# Функция для запуска спайдера с логированием
run_spider() {
    local spider_name=$1
    local count=$2
    local output_file=$3
    local log_file=$4
    
    echo "📊 Запускаем $spider_name (лимит: $count отзывов)"
    
    # Используем python -m scrapy вместо просто scrapy
    nohup $PYTHON_CMD -m scrapy crawl "$spider_name" -a count="$count" -o "$output_file" \
        > "logs/$log_file" 2>&1 &
    
    local pid=$!
    echo "✅ $spider_name запущен с PID: $pid"
    echo "$pid" > "logs/${spider_name}.pid"
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

#!/bin/bash

# Скрипт для параллельного запуска scrapy спайдеров в фоне
# Использование: ./run_parallel_scrapers.sh

# Переходим в директорию проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Запускаем scrapy спайдеры в фоне..."

# Создаем директорию для логов если её нет
mkdir -p logs

# Функция для запуска спайдера с логированием
run_spider() {
    local spider_name=$1
    local count=$2
    local output_file=$3
    local log_file=$4
    
    echo "📊 Запускаем $spider_name (лимит: $count отзывов)"
    
    nohup scrapy crawl "$spider_name" -a count="$count" -o "$output_file" \
        > "logs/$log_file" 2>&1 &
    
    local pid=$!
    echo "✅ $spider_name запущен с PID: $pid"
    echo "$pid" > "logs/${spider_name}.pid"
}

# Запускаем спайдеры
run_spider "banki_all_pages" "1000" "banki_1000.json" "banki_scraper.log"
run_spider "sravni_all_gazprombank_pages" "500" "sravni_500.json" "sravni_scraper.log"

echo ""
echo "🎯 Оба спайдера запущены в фоне!"
echo "📁 Результаты будут сохранены в:"
echo "   - banki_1000.json (лимит: 1000 отзывов)"
echo "   - sravni_500.json (лимит: 500 отзывов)"
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

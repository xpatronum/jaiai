#!/bin/bash

# Скрипт для мониторинга запущенных scrapy процессов
# Использование: ./monitor_scrapers.sh

# Переходим в корневую директорию проекта
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 МОНИТОРИНГ SCRAPY ПРОЦЕССОВ"
echo "================================"
echo "📁 Рабочая директория: $(pwd)"
echo ""

# Проверяем запущенные scrapy процессы
echo "📊 Активные scrapy процессы:"
ps aux | grep -E "(scrapy|python.*crawl)" | grep -v grep | while read line; do
    echo "  ✅ $line"
done

if ! ps aux | grep -E "(scrapy|python.*crawl)" | grep -v grep > /dev/null; then
    echo "  ❌ Нет активных scrapy процессов"
fi

echo ""

# Проверяем PID файлы
echo "📝 PID файлы:"
if [ -f "logs/banki_all_pages.pid" ]; then
    pid=$(cat logs/banki_all_pages.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "  ✅ banki_all_pages (PID: $pid) - работает"
    else
        echo "  ❌ banki_all_pages (PID: $pid) - не работает"
    fi
else
    echo "  ⚠️  PID файл для banki_all_pages не найден"
fi

if [ -f "logs/sravni_all_gazprombank_pages.pid" ]; then
    pid=$(cat logs/sravni_all_gazprombank_pages.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "  ✅ sravni_all_gazprombank_pages (PID: $pid) - работает"
    else
        echo "  ❌ sravni_all_gazprombank_pages (PID: $pid) - не работает"
    fi
else
    echo "  ⚠️  PID файл для sravni_all_gazprombank_pages не найден"
fi

echo ""

# Проверяем размеры выходных файлов
echo "📁 Размеры выходных файлов:"
for file in banki.json sravni.json; do
    if [ -f "$file" ]; then
        size=$(du -h "$file" | cut -f1)
        lines=$(wc -l < "$file" 2>/dev/null || echo "0")
        echo "  📄 $file: $size ($lines строк)"
    else
        echo "  ⚠️  $file: файл не создан"
    fi
done

echo ""

# Показываем последние строки логов
echo "📋 Последние строки логов:"
for log in logs/banki_scraper.log logs/sravni_scraper.log; do
    if [ -f "$log" ]; then
        echo "  📖 $log (последние 3 строки):"
        tail -n 3 "$log" | sed 's/^/    /'
        echo ""
    fi
done

echo "💡 ПОЛЕЗНЫЕ КОМАНДЫ:"
echo "  tail -f logs/banki_scraper.log     # Логи banki.ru в реальном времени"
echo "  tail -f logs/sravni_scraper.log    # Логи sravni.ru в реальном времени"
echo "  kill \$(cat logs/banki_all_pages.pid)  # Остановить banki.ru парсер"
echo "  kill \$(cat logs/sravni_all_gazprombank_pages.pid)  # Остановить sravni.ru парсер"

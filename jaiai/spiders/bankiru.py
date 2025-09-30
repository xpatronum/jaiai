import http
import os
import re
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.exceptions import CloseSpider
from w3lib.html import remove_tags


def normalize_date(date_str):
    """
    Нормализует дату в формат DD.MM.YYYY HH:MM
    Поддерживает как ISO формат, так и уже готовый формат DD.MM.YYYY HH:MM
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    # Если уже в нужном формате (DD.MM.YYYY HH:MM)
    if re.match(r'\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}', date_str):
        return date_str
    
    # Пробуем конвертировать из ISO формата
    try:
        # Убираем 'Z' и заменяем на '+00:00' для корректного парсинга
        iso_date = date_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(iso_date)
        return dt.strftime('%d.%m.%Y %H:%M')
    except:
        # Если не удалось преобразовать, возвращаем как есть
        return date_str


class OnePageSpider(CrawlSpider):
    # name – имя паука
    name = "banki_one_page"
    # allowed_domains – домены сайта, в пределах которого необходимо сканировать
    allowed_domains = ["www.banki.ru"]
    # start_urls – список начальных адресов
    start_urls = ["https://www.banki.ru/investment/responses/list"]

    # rules - правила, определяющие поведение паука
    # первое правило: проваливаемся внутрь отзыва для того, чтобы достать заголовок и текст отзыва
    rules = (
        Rule(
            LinkExtractor(
                restrict_xpaths="//div[@class = 'responses__item__message']/a"
            ),
            callback="parse_item",
            follow=True,
        ),
    )

    def parse_item(self, response):
        item = {}
        title_text = response.xpath("//h1[contains(@class, 'response-page__title')]/text()").get()
        if title_text:
            item["title"] = title_text.strip()
        
        # Собираем весь текст отзыва (все текстовые узлы)
        review_parts = response.xpath("//div[contains(@class, 'article-text')]//text()").getall()
        if review_parts:
            # Объединяем все части, убираем лишние пробелы
            full_review = ' '.join([part.strip() for part in review_parts if part.strip()])
            item["review"] = full_review
        
        # Дата публикации отзыва - пробуем несколько вариантов
        date_published = (
            response.xpath("//meta[@itemprop='datePublished']/@content").get() or
            response.xpath("//time[@itemprop='datePublished']/@datetime").get() or
            response.xpath("//time[@data-test='responses-datetime']/@datetime").get() or
            response.xpath("//time[@pubdate]/@datetime").get()
        )
        if date_published:
            item["date_published"] = normalize_date(date_published)
        
        return item


class AllPagesInvestmentSpider(scrapy.Spider):
    # name – имя паука
    name = "banki_all_pages"
    # allowed_domains – домены сайта, в пределах которого необходимо сканировать
    allowed_domains = ["www.banki.ru"]
    # start_urls – список начальных адресов (Газпромбанк Инвест)
    start_urls = ["https://www.banki.ru/investment/responses/company/broker/gazprombankinvestments/"]
    
    # Настройки для защиты от блокировки
    custom_settings = {
        'DOWNLOAD_DELAY': 3,  # Задержка между запросами (секунды)
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,  # Случайная задержка до 50% от DOWNLOAD_DELAY
        'CONCURRENT_REQUESTS': 1,  # Только 1 одновременный запрос
        'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        'AUTOTHROTTLE_ENABLED': True,  # Автоматическое регулирование скорости
        'AUTOTHROTTLE_START_DELAY': 2,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.0,
        'AUTOTHROTTLE_DEBUG': True,  # Включить отладку автотроттлинга
        'RETRY_TIMES': 5,  # Увеличиваем количество попыток
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 522, 524, 408, 429],  # Добавляем коды для повтора
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }

    def __init__(self, count=None, start_url=None, *args, **kwargs):
        super(AllPagesInvestmentSpider, self).__init__(*args, **kwargs)
        
        # Устанавливаем лимит отзывов
        self.max_count = int(count) if count else None
        self.current_count = 0
        self.should_stop = False  # Флаг принудительной остановки
        
        # Кастомный стартовый URL для возобновления парсинга
        if start_url:
            self.start_urls = [start_url]
            self.logger.info(f"🔄 Кастомный стартовый URL: {start_url}")
        
        if self.max_count:
            self.logger.info(f"🎯 Установлен лимит отзывов: {self.max_count}")
        else:
            self.logger.info("♾️  Лимит отзывов не установлен, парсим все")

    def parse(self, response):
        """Парсинг страницы со списком отзывов"""
        # 🚨 КРИТИЧНО: Проверяем флаг остановки
        if self.should_stop:
            self.logger.info("🛑 Флаг остановки активен, прекращаем парсинг")
            return
        
        # Извлекаем все отзывы со страницы
        reviews = response.xpath("//article[@class='responses__item']")
        self.logger.info(f"📄 Найдено отзывов на странице: {len(reviews)}")
        
        for review in reviews:
            # Проверяем лимит перед обработкой
            if self.max_count and self.current_count >= self.max_count:
                self.logger.info(f"🛑 ЛИМИТ ДОСТИГНУТ: {self.max_count}. ОСТАНАВЛИВАЕМ ПАРСИНГ!")
                self.should_stop = True
                raise CloseSpider(f'Достигнут лимит отзывов: {self.max_count}')
            
            item = {}
            
            # Заголовок отзыва
            title = review.xpath(".//a[@data-test='responses-header']/text()").get()
            if title:
                item["title"] = title.strip()
            
            # Полный текст отзыва (из блока data-full)
            review_text_parts = review.xpath(".//div[@class='responses__item__message markup-inside-small markup-inside-small--bullet' and @data-full]//text()").getall()
            if review_text_parts:
                # Объединяем все части текста
                full_review = ' '.join([part.strip() for part in review_text_parts if part.strip()])
                item["review"] = full_review
            
            # Если нет полного текста, берем превью
            if not item.get("review"):
                preview_parts = review.xpath(".//div[@class='responses__item__message' and @data-preview]//text()").getall()
                if preview_parts:
                    # Фильтруем "Читать далее"
                    preview_text = ' '.join([
                        part.strip() 
                        for part in preview_parts 
                        if part.strip() and 'Читать далее' not in part
                    ])
                    item["review"] = preview_text
            
            # Дата публикации
            date_published = review.xpath(".//time[@data-test='responses-datetime']/@datetime").get()
            if not date_published:
                # Альтернативный вариант - текст внутри time
                date_text = review.xpath(".//time[@data-test='responses-datetime']/text()").get()
                if date_text:
                    item["date_published"] = normalize_date(date_text)
            else:
                item["date_published"] = normalize_date(date_published)
            
            # Увеличиваем счетчик только если элемент валидный
            if item.get("title") or item.get("review"):
                self.current_count += 1
                
                self.logger.info(f"📝 Отзыв {self.current_count}/{self.max_count or '∞'}: {item.get('title', 'Без заголовка')[:50]}...")
                
                # 🚨 КРИТИЧНО: Проверяем лимит сразу после увеличения счетчика
                if self.max_count and self.current_count >= self.max_count:
                    self.logger.info(f"🎉 ЛИМИТ ДОСТИГНУТ! Собрано {self.current_count} отзывов.")
                    self.logger.info(f"🛑 АКТИВИРУЕМ ФЛАГ ОСТАНОВКИ!")
                    self.should_stop = True
                    yield item
                    raise CloseSpider(f'Лимит отзывов достигнут: {self.current_count}/{self.max_count}')
                
                yield item
        
        # Переход на следующую страницу (пагинация)
        if not self.should_stop:
            next_page = response.xpath("//li[@class='ui-pagination__item ui-pagination__next']/a/@href").get()
            if next_page:
                next_page_url = response.urljoin(next_page)
                self.logger.info(f"➡️  Переход на следующую страницу: {next_page_url}")
                yield scrapy.Request(next_page_url, callback=self.parse)

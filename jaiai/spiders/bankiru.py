import http
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.exceptions import CloseSpider
from w3lib.html import remove_tags


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
        item["title"] = (
            response.xpath("//h1[contains(@class, 'response-page__title')]/text()")
            .get()
            .strip()
        )
        item["review"] = (
            response.xpath("//div[contains(@class, 'article-text')]/text()")
            .get()
            .strip()
        )
        return item


class AllPagesInvestmentSpider(CrawlSpider):
    # name – имя паука
    name = "banki_all_pages"
    # allowed_domains – домены сайта, в пределах которого необходимо сканировать
    allowed_domains = ["www.banki.ru"]
    # start_urls – список начальных адресов
    start_urls = ["https://www.banki.ru/investment/responses/list"]
    """
    rules - правила, определяющие поведение паука
    первое правило: проваливаемся внутрь отзыва для того, чтобы достать заголовок и текст отзыва
    второе правило: переходим по страницам
    """
    rules = (
        Rule(
            LinkExtractor(
                restrict_xpaths="//div[@class = 'responses__item__message']/a"
            ),
            callback="parse_item",
            follow=True,
        ),
        Rule(
            LinkExtractor(
                restrict_xpaths="//li[@class='ui-pagination__item ui-pagination__next']/a"
            )
        ),
    )

    def __init__(self, count=None, *args, **kwargs):
        super(AllPagesInvestmentSpider, self).__init__(*args, **kwargs)
        # Устанавливаем лимит отзывов
        self.max_count = int(count) if count else None
        self.current_count = 0
        self.should_stop = False  # Флаг принудительной остановки
        
        if self.max_count:
            self.logger.info(f"🎯 Установлен лимит отзывов: {self.max_count}")
        else:
            self.logger.info("♾️  Лимит отзывов не установлен, парсим все")

    def parse_item(self, response):
        # 🚨 КРИТИЧНО: Проверяем флаг остановки в самом начале
        if self.should_stop:
            self.logger.info("🛑 Флаг остановки активен, пропускаем обработку")
            return None
            
        # Проверяем лимит перед обработкой
        if self.max_count and self.current_count >= self.max_count:
            self.logger.info(f"🛑 ЛИМИТ УЖЕ ДОСТИГНУТ: {self.max_count}. АКТИВИРУЕМ ФЛАГ ОСТАНОВКИ!")
            self.should_stop = True
            raise CloseSpider(f'Достигнут лимит отзывов: {self.max_count}')
        
        item = {}
        title = response.xpath("//h1[contains(@class, 'response-page__title')]/text()").get()
        review = response.xpath("//div[contains(@class, 'article-text')]//text()").get()
        
        if title:
            item["title"] = title.strip()
        if review:
            item["review"] = review.strip()
        
        # Увеличиваем счетчик только если элемент валидный
        if item.get("title") or item.get("review"):
            self.current_count += 1
            
            self.logger.info(f"📝 Отзыв {self.current_count}/{self.max_count or '∞'}: {item.get('title', 'Без заголовка')[:50]}...")
            
            # 🚨 КРИТИЧНО: Проверяем лимит сразу после увеличения счетчика
            if self.max_count and self.current_count >= self.max_count:
                self.logger.info(f"🎉 ЛИМИТ ДОСТИГНУТ! Собрано {self.current_count} отзывов.")
                self.logger.info(f"🛑 АКТИВИРУЕМ ФЛАГ ОСТАНОВКИ И ПОДНИМАЕМ ИСКЛЮЧЕНИЕ!")
                self.should_stop = True
                raise CloseSpider(f'Лимит отзывов достигнут: {self.current_count}/{self.max_count}')
            
            return item
        
        return None

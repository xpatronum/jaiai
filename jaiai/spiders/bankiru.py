import http
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
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

    def parse_item(self, response):
        item = {}
        item["title"] = (
            response.xpath("//h1[contains(@class, 'response-page__title')]/text()")
            .get()
            .strip()
        )
        item["review"] = (
            response.xpath("//div[contains(@class, 'article-text')]//text()")
            .get()
            .strip()
        )
        return item

import scrapy
import json
import re
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from w3lib.html import remove_tags


class SravniGazprombankSpider(CrawlSpider):
    """
    Спайдер для парсинга отзывов о Газпромбанке с сайта sravni.ru
    """
    name = "sravni_gazprombank"
    allowed_domains = ["sravni.ru"]
    start_urls = ["https://www.sravni.ru/bank/gazprombank/otzyvy/"]

    # Пользовательский агент для избежания блокировок
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'DOWNLOAD_DELAY': 2,  # Задержка между запросами
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,  # Случайная задержка
    }

    rules = (
        # Правило для пагинации (переход по страницам)
        Rule(
            LinkExtractor(
                restrict_xpaths="//a[contains(@class, 'pagination') or contains(text(), 'Следующая') or contains(@class, 'next') or contains(@href, '?page=')]"
            ),
            callback="parse_page",
            follow=True,
        ),
    )

    def parse_start_url(self, response):
        """
        Парсинг стартовой страницы для извлечения отзывов из JSON-LD
        """
        return self.parse_page(response)

    def parse_page(self, response):
        """
        Парсинг страницы с отзывами из JSON-LD структуры
        """
        # Ищем JSON-LD скрипт с отзывами
        json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        
        for script_content in json_ld_scripts:
            try:
                # Парсим JSON
                json_data = json.loads(script_content)
                
                # Если это список, берем первый элемент
                if isinstance(json_data, list):
                    json_data = json_data[0]
                
                # Проверяем, что это структура с отзывами
                if json_data.get('@type') == 'Product' and 'reviews' in json_data:
                    reviews = json_data['reviews']
                    
                    for review_data in reviews:
                        item = self.extract_review_from_json(review_data, response)
                        if item:
                            yield item
                            
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                self.logger.warning(f"Ошибка парсинга JSON-LD: {e}")
                continue

    def extract_review_from_json(self, review_data, response):
        """
        Извлечение данных отзыва из JSON структуры
        """
        if review_data.get('@type') != 'Review':
            return None
            
        item = {}
        
        # Заголовок отзыва
        title = review_data.get('name')
        if title:
            item['title'] = title.strip()
        
        # Текст отзыва (убираем HTML теги)
        review_body = review_data.get('reviewBody')
        if review_body:
            # Убираем HTML теги и лишние пробелы
            clean_text = remove_tags(review_body)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            item['review'] = clean_text
        
        return item if (item.get('title') or item.get('review')) else None


class SravniAllGarpormbankPagesSpider(scrapy.Spider):
    """
    Спайдер с ручным перебором страниц через URL параметры
    """
    name = "sravni_all_gazprombank_pages"
    allowed_domains = ["sravni.ru"]
    
    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'DOWNLOAD_DELAY': 2,
        'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
    }
    
    def start_requests(self):
        # Пробуем различные паттерны URL для пагинации
        base_url = "https://www.sravni.ru/bank/gazprombank/otzyvy/"
        
        url_patterns = [
            # Стандартные паттерны пагинации
            f"{base_url}?page={{}}",
            f"{base_url}?p={{}}",
            f"{base_url}page/{{}}",
            f"{base_url}?offset={{}}",
            f"{base_url}?limit=20&offset={{}}",
            f"{base_url}?per_page=20&page={{}}",
            # Специфичные для sravni.ru
            f"{base_url}?reviews_page={{}}",
            f"{base_url}?tab=reviews&page={{}}",
        ]
        
        # Пробуем первые 10 страниц для каждого паттерна
        for pattern in url_patterns:
            for page in range(1, 11):
                url = pattern.format(page)
                if page == 1:
                    offset = 0
                else:
                    offset = (page - 1) * 20
                    
                # Для offset паттернов используем другую логику
                if 'offset' in pattern:
                    url = pattern.format(offset)
                
                yield scrapy.Request(
                    url=url,
                    callback=self.parse_page,
                    meta={'page': page, 'pattern': pattern}
                )

    def parse_page(self, response):
        """
        Парсинг страницы с отзывами
        """
        page = response.meta['page']
        pattern = response.meta['pattern']
        
        # Извлекаем отзывы из JSON-LD
        reviews_found = 0
        json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        
        for script_content in json_ld_scripts:
            try:
                json_data = json.loads(script_content)
                if isinstance(json_data, list):
                    json_data = json_data[0]
                
                if json_data.get('@type') == 'Product' and 'reviews' in json_data:
                    reviews = json_data['reviews']
                    
                    for review_data in reviews:
                        item = self.extract_review_from_json(review_data, response)
                        if item:
                            item['page_number'] = page
                            item['url_pattern'] = pattern
                            reviews_found += 1
                            yield item
                            
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        
        # Логируем результаты
        if reviews_found > 0:
            self.logger.info(f"✅ Найдено {reviews_found} отзывов на странице {page} по паттерну: {pattern}")
        else:
            self.logger.info(f"❌ Отзывы не найдены на странице {page} по паттерну: {pattern}")

    def extract_review_from_json(self, review_data, response):
        """Извлечение отзыва из JSON"""
        if review_data.get('@type') != 'Review':
            return None
            
        item = {}
        
        title = review_data.get('name')
        if title:
            item['title'] = title.strip()
        
        review_body = review_data.get('reviewBody')
        if review_body:
            clean_text = remove_tags(review_body)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            item['review'] = clean_text
        
        return item if (item.get('title') or item.get('review')) else None
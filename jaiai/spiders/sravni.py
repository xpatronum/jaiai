import scrapy
import json
import re
import html
from datetime import datetime
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from scrapy.exceptions import CloseSpider
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
        'DOWNLOAD_DELAY': 1,  # Задержка между запросами
        'RANDOMIZE_DOWNLOAD_DELAY': 0.25,  # Случайная задержка
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

    def clean_json_string(self, json_string):
        """
        Очистка JSON строки от недопустимых символов
        """
        try:
            # Убираем недопустимые управляющие символы (кроме допустимых)
            # Допустимые: \t \n \r и экранированные символы
            cleaned = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', json_string)
            
            # Дополнительная очистка - убираем некорректные unicode последовательности
            cleaned = cleaned.encode('utf-8', errors='ignore').decode('utf-8')
            
            return cleaned
        except Exception as e:
            self.logger.warning(f"Ошибка очистки JSON строки: {e}")
            return json_string

    def parse_page(self, response):
        """
        Парсинг страницы с отзывами из JSON-LD структуры
        """
        self.logger.info(f"Парсинг страницы: {response.url}")
        
        # Ищем JSON-LD скрипт с отзывами
        json_ld_scripts = response.xpath('//script[@type="application/ld+json"]/text()').getall()
        
        reviews_count = 0
        
        for i, script_content in enumerate(json_ld_scripts):
            try:
                self.logger.info(f"Обрабатываем JSON-LD скрипт #{i+1}")
                
                # Шаг 1: Очистка недопустимых символов
                cleaned_content = self.clean_json_string(script_content)
                
                # Шаг 2: Пробуем несколько вариантов декодирования
                json_data = None
                
                # Вариант 1: Прямой парсинг
                try:
                    json_data = json.loads(cleaned_content)
                    self.logger.info("JSON распарсен напрямую")
                except json.JSONDecodeError as e1:
                    self.logger.info(f"Прямой парсинг не удался: {e1}")
                    
                    # Вариант 2: С декодированием unicode escape
                    try:
                        decoded_content = cleaned_content.encode('utf-8').decode('unicode_escape')
                        # Дополнительная очистка после декодирования
                        decoded_content = self.clean_json_string(decoded_content)
                        json_data = json.loads(decoded_content)
                        self.logger.info("JSON распарсен с unicode decode")
                    except (json.JSONDecodeError, UnicodeDecodeError) as e2:
                        self.logger.info(f"Unicode декодирование не удалось: {e2}")
                        
                        # Вариант 3: Более агрессивная очистка
                        try:
                            # Убираем все что между quotes и может вызывать проблемы
                            aggressive_clean = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', cleaned_content)
                            json_data = json.loads(aggressive_clean)
                            self.logger.info("JSON распарсен с агрессивной очисткой")
                        except json.JSONDecodeError as e3:
                            self.logger.warning(f"Все варианты парсинга не удались: {e3}")
                            continue
                
                if not json_data:
                    continue
                
                # Если это список, берем первый элемент
                if isinstance(json_data, list):
                    json_data = json_data[0]
                
                # Проверяем, что это структура с отзывами
                if json_data.get('@type') == 'Product' and 'reviews' in json_data:
                    reviews = json_data['reviews']
                    self.logger.info(f"Найдено {len(reviews)} отзывов в JSON-LD")
                    
                    for review_data in reviews:
                        item = self.extract_review_from_json(review_data, response)
                        if item:
                            reviews_count += 1
                            yield item
                else:
                    self.logger.info(f"JSON-LD не содержит отзывы. Тип: {json_data.get('@type')}")
                            
            except Exception as e:
                self.logger.warning(f"Общая ошибка обработки JSON-LD #{i+1}: {e}")
                # Дополнительно логируем первые 200 символов для отладки
                preview = script_content[:200] if script_content else "пустой"
                self.logger.debug(f"Превью содержимого: {preview}...")
                continue
        
        self.logger.info(f"Извлечено {reviews_count} отзывов со страницы {response.url}")

    def extract_review_from_json(self, review_data, response):
        """
        Извлечение данных отзыва из JSON структуры
        """
        if review_data.get('@type') != 'Review':
            self.logger.debug(f"Неверный тип отзыва: {review_data.get('@type')}")
            return None
            
        item = {}
        
        # Заголовок отзыва
        title = review_data.get('name')
        if title:
            try:
                # Декодируем HTML entities и unicode
                title = html.unescape(str(title))
                item['title'] = title.strip()
            except Exception as e:
                self.logger.warning(f"Ошибка обработки заголовка: {e}")
                item['title'] = str(title).strip()
        
        # Текст отзыва (убираем HTML теги)
        review_body = review_data.get('reviewBody')
        if review_body:
            try:
                # Преобразуем в строку на всякий случай
                review_body = str(review_body)
                
                # Декодируем HTML entities
                decoded_body = html.unescape(review_body)
                
                # Убираем HTML теги
                clean_text = remove_tags(decoded_body)
                
                # Убираем лишние пробелы и переносы строк
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                if clean_text:
                    item['review'] = clean_text
                    
            except Exception as e:
                self.logger.warning(f"Ошибка обработки reviewBody: {e}")
                # Fallback - просто убираем HTML теги без декодирования
                try:
                    clean_text = remove_tags(str(review_body))
                    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                    if clean_text:
                        item['review'] = clean_text
                except:
                    pass
        
        # Дата публикации отзыва
        date_published = review_data.get('datePublished')
        if date_published:
            try:
                # Конвертируем из ISO формата в "DD.MM.YYYY HH:MM"
                date_str = str(date_published).strip()
                
                # Парсим ISO дату
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                
                # Форматируем в нужный вид
                formatted_date = dt.strftime('%d.%m.%Y %H:%M')
                item['date_published'] = formatted_date
                
            except Exception as e:
                self.logger.warning(f"Ошибка обработки даты: {e}, оставляем как есть")
                # Если не удалось преобразовать, оставляем как есть
                item['date_published'] = str(date_published).strip()
        
        # Проверяем, что у нас есть хотя бы заголовок или текст
        if not (item.get('title') or item.get('review')):
            self.logger.debug(f"Отзыв не содержит ни заголовка, ни текста")
            return None
        
        self.logger.debug(f"Извлечен отзыв: {item.get('title', 'Без заголовка')[:50]}...")
        return item


# Остальные классы остаются без изменений...
class SravniAllGazprombankPagesSpider(scrapy.Spider):
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
    
    def __init__(self, count=None, *args, **kwargs):
        super(SravniAllGazprombankPagesSpider, self).__init__(*args, **kwargs)
        # Устанавливаем лимит отзывов
        self.max_count = int(count) if count else None
        self.current_count = 0
        self.should_stop = False  # Флаг принудительной остановки
        
        if self.max_count:
            self.logger.info(f"🎯 Установлен лимит отзывов: {self.max_count}")
        else:
            self.logger.info("♾️  Лимит отзывов не установлен, парсим все")
    
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
        
        # 🚨 КРИТИЧНО: Проверяем флаг остановки в самом начале
        if self.should_stop:
            self.logger.info(f"🛑 Флаг остановки активен, пропускаем страницу {page}")
            return
        
        # Проверяем, не достигли ли мы лимита
        if self.max_count and self.current_count >= self.max_count:
            self.logger.info(f"🛑 ЛИМИТ УЖЕ ДОСТИГНУТ: {self.max_count}. Пропускаем страницу {page}")
            self.should_stop = True
            raise CloseSpider(f'Достигнут лимит отзывов: {self.max_count}')
        
        # Используем тот же метод извлечения что и в основном спайдере
        gazprombank_spider = SravniGazprombankSpider()
        
        reviews_found = 0
        for item in gazprombank_spider.parse_page(response):
            # 🚨 КРИТИЧНО: Проверяем флаг остановки перед обработкой каждого элемента
            if self.should_stop:
                self.logger.info("🛑 Флаг остановки активен, прекращаем обработку элементов")
                return
                
            if item:
                # Проверяем лимит перед добавлением элемента
                if self.max_count and self.current_count >= self.max_count:
                    self.logger.info(f"🛑 ЛИМИТ ДОСТИГНУТ перед добавлением: {self.max_count}. АКТИВИРУЕМ ФЛАГ ОСТАНОВКИ!")
                    self.should_stop = True
                    raise CloseSpider(f'Достигнут лимит отзывов: {self.max_count}')
                
                self.current_count += 1
                
                reviews_found += 1
                self.logger.info(f"📝 Отзыв {self.current_count}/{self.max_count or '∞'}: {item.get('title', 'Без заголовка')[:50]}...")
                
                yield item
                
                # 🚨 КРИТИЧНО: Проверяем лимит сразу после добавления
                if self.max_count and self.current_count >= self.max_count:
                    self.logger.info(f"🎉 ЛИМИТ ДОСТИГНУТ! Собрано {self.current_count} отзывов.")
                    self.logger.info(f"🛑 АКТИВИРУЕМ ФЛАГ ОСТАНОВКИ И ПОДНИМАЕМ ИСКЛЮЧЕНИЕ!")
                    self.should_stop = True
                    raise CloseSpider(f'Лимит отзывов достигнут: {self.current_count}/{self.max_count}')
        
        # Логируем результаты
        if reviews_found > 0:
            self.logger.info(f"✅ Найдено {reviews_found} отзывов на странице {page} по паттерну: {pattern}")
        else:
            self.logger.info(f"❌ Отзывы не найдены на странице {page} по паттерну: {pattern}")
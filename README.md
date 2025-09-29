## 📦 Installation

Make sure you have Python and Scrapy installed:

```bash
git clone https://github.com/xpatronum/jaiai && cd jaiai

pip install -r requirements.txt
```


## 🕷️ Scrapping

Welcome to the Scrapping Project! This project uses **Scrapy** to collect investment reviews from [banki.ru](https://www.banki.ru). Follow the steps below to get started. 🚀


## 🏁 How to Run the Scrapy Spider

To start scrapping all investment review pages, use the following command in your terminal:

```bash
scrapy crawl all_pages
```

Or, to scrape just one page:

```bash
scrapy crawl one_page
```

## 🌐 Example

```bash
scrapy crawl banki_all_pages -o all_pages_banki_result.json
```

This will save the results to `all_pages_banki_result.json`.

```bash
scrapy crawl sravni_all_gazprombank_pages -o all_pages_sravni_result.json
```

## 📂 Output

Scraped data will be saved according to your spider's settings (e.g., JSON, CSV, or database).

## 💡 Tips

- Check your spider code for custom settings.
- Use `-o output.json` to save results to a file.

## 🛠️ Happy Scrapping!

---

### Powered by `justatom.org`
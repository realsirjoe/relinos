<div align="center">

[English](README.md) · [简体中文](README_zh.md) · [日本語](README_ja.md) · **Русский** · [Português](README_pt.md)

# Relinos

### Программируемый браузер, который превращает сайты в API.

REST API для **рендеринга** и **взаимодействия** с сайтами, управления **несколькими браузерами** и извлечения **структурированных данных**

</div>

![Демонстрация Relinos](https://raw.githubusercontent.com/realsirjoe/designs/master/relinos_demo.gif)

# Начало работы

Relinos работает в Linux и macOS.

**Установка**
 
```bash
git clone https://github.com/realsirjoe/relinos
cd relinos
python3 relinos/install.py
```

**Запуск**
```bash
bash relinos/start.sh
```

После запуска вы можете рендерить любой сайт и взаимодействовать с ним через **/get**.
Единственный обязательный параметр — `url`.

Выполните следующий пример в терминале, чтобы убедиться, что всё работает. Он извлекает результаты поиска DuckDuckGo.

```bash
curl -X GET http://localhost:8032/get \
  -H 'Content-Type: application/json' \
  --data-binary @- <<'JSON'
{
    "url": "https://duckduckgo.com/?q=dogs",
    "render": true,
    "format": "json",
    "extraction": {
        "results": {
            "$xpath": "//*[@data-testid='result']",
            "$list": true,
            "url": { "$xpath": ".//*[@data-testid='result-extras-url-link']/@href" },
            "title": { "$xpath": ".//*[@data-testid='result-title-a']" },
            "description": { "$xpath": ".//*[@data-result='snippet']" }
        }
    }
}
JSON
```

При использовании `"format": "json"` параметр `extraction` определяет структуру JSON, которую вы хотите получить. Можно использовать любые имена ключей, например `results`, `title` или `description`. Свойство `$xpath` указывает, где на странице искать соответствующие данные.

Используйте `$list: true`, чтобы извлечь несколько совпадающих элементов, а не только первый. Также можно вкладывать объекты друг в друга для извлечения более сложных структур.
Например, каждый `result` может содержать `url`, `title` и `description`.

[Подробнее об извлечении данных](#извлечение-данных)

## Общие сценарии для сайтов

Вы можете импортировать готовые сценарии и настройки извлечения из [Relinos Registry](https://github.com/realsirjoe/relinos_registry).

Просто скопируйте JSON-файл и передайте его в теле POST-запроса к API-эндпоинту **/import**.

<img src="https://www.google.com/s2/favicons?domain=google.com&sz=64" width="20" height="20" align="absmiddle"> **Поиск Google** | [Сценарий](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_search.json) | [Настройка извлечения](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=maps.google.com&sz=64" width="20" height="20" align="absmiddle"> **Поиск в Google Картах** | [Сценарий](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_maps_search.json) | [Настройка извлечения](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_maps_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=youtube.com&sz=64" width="20" height="20" align="absmiddle"> **Поиск YouTube** | [Сценарий](https://github.com/realsirjoe/relinos_registry/blob/master/routines/youtube_com_search.json) | [Настройка извлечения](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/youtube_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=duckduckgo.com&sz=64" width="20" height="20" align="absmiddle"> **Поиск DuckDuckGo** | [Сценарий](https://github.com/realsirjoe/relinos_registry/blob/master/routines/duckduckgo_com_search.json) | [Настройка извлечения](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/duckduckgo_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=ebay.com&sz=64" width="20" height="20" align="absmiddle"> **Поиск eBay** | [Сценарий](https://github.com/realsirjoe/relinos_registry/blob/master/routines/ebay_com_search.json) | [Настройка извлечения](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/ebay_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=skyscanner.com&sz=64" width="20" height="20" align="absmiddle"> **Поиск авиарейсов Skyscanner** | [Сценарий](https://github.com/realsirjoe/relinos_registry/blob/master/routines/skyscanner_com_flight_search.json) | [Настройка извлечения](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/skyscanner_com_flights.json)

Например, через **/do** можно легко выполнить поиск в Google:

```bash
curl --request GET \
  --url http://0.0.0.0:8032/do \
  --header 'Content-Type: application/json' \
  --data '{
    "name": "google_com_search",
    "params": { "search_term": "dog", "max_pages": "1"},
    "format": "json"
}'
```

После импорта ваши приложения или LLM могут выполнять сценарии через API.

## Создание собственных сценариев

Relinos позволяет объединить взаимодействия с браузером, пагинацию, кэширование и структурированное извлечение в одном JSON-запросе, например:
```json
{
    "url": "https://www.google.com",
    "render": true,
    "actions": [
        ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
        ["actionType","your search term",""],
        ["actionSleep", "1", ""],
        ["actionKeyboardEnter", "", ""],
        ["actionSleep", "2", ""]
    ],
    "pagination": ["//*[@id='pnnext']", 2],
    "cache": "1d",
    "format": "json",
    "extraction": {
        "query": { "$xpath": "//*[@id='ti6dpd']" },
        "result_count": {
            "$xpath": "//div[@class='XhWQv qd6zO ApHyTb']",
            "$extract": "\\D*(\\d[,\\d]*) .*"
        },
        "ai": {
            "$xpath": "//*[@class='mZJni Dn7Fzd']", "$format": "md"
        },
        "results": {
            "$xpath": "//div[contains(@class, 'MjjYud')]",
            "$list": true,
            "title": { "$xpath": ".//h3[contains(@class, 'LC20lb MBeuO DKV0Md')]" },
            "url": { "$xpath": ".//a[contains(@class, 'zReHs')]/@href" },
            "site": { "$xpath": ".//span[contains(@class, 'VuuXrf')]" },
            "snippet": { "$xpath": ".//div[contains(@data-snf, 'nke7rc')]" }
        },
        "related_searches": {
            "$xpath": "//*[@class='qR29te']", "$list": true
        }
    }
}
```


|Параметр   |Описание                                                               |Пример                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|url         | Загружает указанный URL                                                        | `"https://example.com"`               |
|render      | Рендерит сайт в реальном браузере                                  | `true` или `false`                   |
|cache       | Использует кэшированный результат, если он получен не более указанного времени назад     | `"600s"`, `"60m"`, `"2h"`, `"7d"` или `"1y"` |
|debug       | Возвращает заголовок `x-debug-url`; перейдите по этому URL, чтобы проверить и отладить взаимодействие   | `true` или `false`    |
|includeMeta | Оборачивает ответ метаинформацией                               | `true` или `false`                       |
|proxy       | Использует заданный прокси http, https или socks5; необходимо указать схему       | `http://127.0.0.1:1080` или `socks5://12.98.4.2:1988`          |
|format      | Формат вывода                                                        | `"html"`, `"md"` или `"json"`            |
|actions     | Список выполняемых взаимодействий с сайтом; [см. «Взаимодействия»](#взаимодействия) | `[["actionSelect", "//div[@id='email']", ""],["actionClick", "", ""]]`  |
|pagination  | Разбивает запрос на несколько страниц. Это JSON-массив с XPath URL следующей страницы и числом страниц, которые нужно получить | `["//a[@id='nextpage']", 2]`  |
|extraction   | Укажите имя сохранённой настройки извлечения или полную настройку. Требуется `format: "json"`. Не забудьте экранировать регулярные выражения, чтобы JSON оставался корректным. Чтобы применить настройку к итоговому HTML, [см. «Извлечение данных»](#извлечение-данных)  | `"google_com_search_results"`           |

В ответе будет возвращён итоговый сайт после всех взаимодействий в указанном **format**. При **includeMeta** будет возвращён JSON, в котором итоговый сайт находится в ключе **data**.

## Взаимодействия

Взаимодействия с браузером, такие как щелчки и ввод текста, выполняются через параметр `actions`.
`actions` — это список массивов, каждый из которых содержит имя действия и 2 параметра.

`actionClick` и `actionType` взаимодействуют с текущим выбранным элементом; см. actionSelect и actionFilter*.


|Действие                 |Параметр 1        |Параметр 2             |
|-----------------------|---------------|--------------------|
|actionSleep            |количество секунд  |-                   |
|actionClick            |-              |-                   |
|actionType             |текст           |-                   |
|actionKeyboardEnter    |-              |-                   |
|actionSelect           |XPath          |-                   |
|actionWaitForAndSelect |XPath          |максимальное время ожидания в секундах |
|actionFilterText       |текст, который должен содержать элемент|-                   |
|actionFilterAttribute  |имя атрибута | значение атрибута    |
|actionFilterIndex      |индекс          |-                   |
|actionExecuteScript    |JavaScript     |-                   |
|actionGoTo             |URL            |-                   |


Этот пример выполняет поиск на сайте:
```json
[
    ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
    ["actionType", "My Search Query", ""],
    ["actionKeyboardEnter", "", ""],
    ["actionSleep", "2", ""]
]
```

В зависимости от действия за ним могут следовать не более 2 аргументов.

Чтобы сохранить сценарий и затем использовать его повторно, задайте ему имя и параметры.

Для начала замените **/get** на **POST /routines/your_routine_name**.

Поскольку сценарий обычно должен принимать входные данные, например поисковый запрос или учётные данные, `params` указывает, куда поместить эти значения. Также можно добавить `description` как для сценария, так и для каждого параметра. Если сценарий уже существует, для его перезаписи необходимо указать **overwrite=true** в качестве параметра запроса.

|Ключ параметра      |Описание                               |
|---------------|------------------------------------------|
|name           | имя параметра                    |
|description    |                                          |
|patches        | список патчей; см. patch               |
|default        | значение по умолчанию, если параметр не указан   |
|kind           | например, `"int"`, `"float"`, `"str"`, `"date"`       |

|Ключ патча      |Описание                                                                     |
|---------------|--------------------------------------------------------------------------------|
|keypath        |точечная нотация, описывающая, куда поместить параметр                                  |
|start          |позиция в строке, с которой начинается вставка                                   |
|end            |позиция в строке, до которой исходное содержимое заменяется             |
|transform      |предопределённая функция для применения к параметру: url_quote или url_query_quote     |

Для сложных взаимодействий рекомендуется использовать несколько сценариев: например, один для поиска, другой для покупки товара и т. д.

Ниже приведён параметризованный сценарий, готовый к сохранению:
```json
{
    "name": "google_search",
    "description": "",
    "params": [
        {
            "name": "search_term",
            "description": "",
            "patches": [{"keypath": "actions.1.v0"}],
            "default": ""
        },
        {
            "name": "max_pages",
            "description": "",
            "patches": [{"keypath": "pagination.maxPages"}],
            "default": "",
            "kind": "int"
        }
    ],
    "url": "https://www.google.com",
    "render": true,
    "actions": [
        ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
        ["actionType", "searchTerm", ""],
        ["actionSleep", "1", ""],
        ["actionKeyboardEnter", "", ""],
        ["actionSleep", "2", ""]
    ],
    "pagination": ["//*[@id='pnnext']", "3"],
    "extraction": ""
}
```

Сценарии можно запускать с помощью **/do**: в теле JSON используйте `name` для указания сценария, а в `params` задайте необходимые параметры, например `"params": { "search_term": "How old is the earth" }`.

Удалить сценарий можно через **DELETE /routines/your_routine_name**.

Также можно просмотреть все сценарии через **/routines** и искать их через **/routines?q=search_term**.


## Извлечение данных

HTML любой страницы можно преобразовать в Markdown; см. `format`.

Relinos также поддерживает извлечение и проверку структурированных данных с помощью нового расширяемого и простого формата.

XPathSchema структурирует данные в виде дерева, поскольку большая часть информации в интернете представлена в такой форме через HTML. Формат является корректным JSON, поэтому его легко понимать и анализировать.

Пример XPathSchema:

```json
{
    "results": {
        "$xpath": "//*[contains(@class, 'Ww4FFb')]",
        "$list": true,
        "url": {
            "$xpath": ".//*[contains(@class, 'zReHs')]/@href",
            "$pattern": "https://.*"
        },
        "title": {
            "$xpath": ".//h3"
        },
        "description": {
            "$xpath": ".//*[contains(@class, 'VwiC3b yXK7lf p4wth r025kc Hdw6tb')]"
        }
    },
    "people_also_search_for": {
        "$xpath": "//*[@class='ngTNl ggLgoc']",
        "$list": true
    }
}
```
Это схема для поиска Google.
Она описывает структуру данных через отношения между родительскими и дочерними элементами.
Есть обычные ключи, описывающие сами данные, и специальные ключи, начинающиеся с `$`.

Например, `$xpath` определяет, в какой части HTML находятся данные.
Таким образом можно указать, как найти каждый результат поиска Google, а в каждом результате — заголовок, URL и описание.

Следовательно, сам формат уже показывает, какую итоговую структуру будут иметь извлечённые данные.
Он создаст такие данные:

```json
{
    "results": [
        {
            "url": "https://en.wikipedia.org/wiki/Ferrari_348",
            "title": "Ferrari 348",
            "description": "The Ferrari 348 (Type F119) is a mid-engined, V8-powered..."
        },
        {
            "url": "https://www.autoscout24.hr/lst/ferrari/348",
            "title": "85 Rezultati za Ferrari 348",
            "description": null
        }
    ],
    "people_also_search_for": [
        "Ferrari 348 for sale",
        "Ferrari 348 price",
        "Ferrari 348 TS",
        "Ferrari 348 GTB",
        "Ferrari 348 Spider",
        "Ferrari 348 GTS"
    ]
}
```

|Специальный ключ |Описание                                                               |Пример                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|$xpath      | XPath, описывающий, как найти данные                              | `"//div[@class='price']"`             |
|$pattern    | регулярное выражение для сопоставления данных перед `$extract` и `$transform`             | `"\\d[\\.\\d+]?"`                        |
|$required   | данные должны существовать                                                          | `true` или `false`                       |
|$list       | Возвращает все совпадающие элементы списком вместо первого результата.      | `true` или `false`                       |
|$format     | Способ форматирования выбранного HTML; родительские элементы игнорируют формат           | `"text"`, `"html"` или `"md"`            |
|$transform  | Использует предопределённые функции для преобразования данных                              | скоро будет доступно                         |
|$extract    | Извлекает строковые данные с помощью регулярного выражения, сохраняя первую захватывающую группу; обязательно экранируйте `\\`  | `"(\\d[\\.\\d+]?)US$"`                   |

Если вы хотите повторно использовать настройки извлечения позднее, добавьте их, отправив тело запроса **/get** или **/do** на **POST /extractions/your_extraction_name**. В тело также можно добавить ключ `description`.

Удалить их можно с помощью **DELETE /extractions/your_extraction_name**.

Просмотреть все настройки извлечения можно через **/extractions**, а искать их — через **/extractions?q=search_term**.

## Обработка ошибок

2xx — запрос выполнен успешно.

4xx — запрос не выполнен из-за ошибки на стороне клиента, например недопустимых параметров или отсутствующего ресурса.

5xx — при обработке запроса на сервере произошла ошибка.

Ошибки возвращаются в формате JSON; `detail` содержит дополнительную информацию об ошибке.

## Конфигурация

Чтобы изменить настройки Relinos, отредактируйте **~/.relinos/config**.

Каждая настройка имеет формат `VARIABLE=VALUE`.

|переменная            |Описание                              |Пример             |
|--------------------|-----------------------------------------|--------------------|
|PORT                | Порт, на котором прослушивает API           | `1081`             |
|BROWSER_WORKER_PORT | Порт, на котором прослушивает воркер браузера| `18765`            |
|BROWSER_POOL_SIZE   | Количество запускаемых экземпляров браузера      | `2` или `10`        |

Чтобы изменения конфигурации вступили в силу, перезапустите Relinos.

---

> Этот документ переведён с помощью LLM. За исходной информацией обращайтесь к [README.md](README.md).

<div align="center">

**English** | [简体中文](README_zh.md)
# Relinos

### A programmable browser that turns sites into APIs.

REST API to **render** and **interact** with sites, control **multiple browsers** and extract **structured data**

</div>

![Relinos Demo](https://raw.githubusercontent.com/realsirjoe/designs/master/relinos_demo.gif)

# Getting Started

Relinos runs on Linux and macOS

**Install**
 
```bash
git clone https://github.com/realsirjoe/relinos
cd relinos
python3 relinos/install.py
```

**Start** 
```bash
bash relinos/start.sh
```

Once started, you can render and interact with any site via **/get** 
The only required parameter is `url`

Try this example in your terminal to verify that everything works. It extracts DuckDuckGo search results.

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

When using `"format": "json"`, an `extraction` defines the structure of the JSON you want to retrieve. You can use any key names, such as `results`, `title`, or `description`. The `$xpath` property specifies where to find the corresponding data on the page.

Use `$list: true` to extract multiple matching elements instead of just one. You can also nest objects to extract more complex structures.
For example, each `result` could contain a `url`, `title`, and `description`.

[More on Extractions](#extraction) 

## Shared Site Routines

You can import ready-to-use routines and extractions from the [Relinos Registry](https://github.com/realsirjoe/relinos_registry).

Simply copy a JSON file and put it in the body of the POST **/import** API endpoint

<img src="https://www.google.com/s2/favicons?domain=google.com&sz=64" width="20" height="20" align="absmiddle"> **Google Search** | [Routine](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_search.json) | [Extraction](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=maps.google.com&sz=64" width="20" height="20" align="absmiddle"> **Google Maps Search** | [Routine](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_maps_search.json) | [Extraction](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_maps_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=youtube.com&sz=64" width="20" height="20" align="absmiddle"> **YouTube Search** | [Routine](https://github.com/realsirjoe/relinos_registry/blob/master/routines/youtube_com_search.json) | [Extraction](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/youtube_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=duckduckgo.com&sz=64" width="20" height="20" align="absmiddle"> **DuckDuckGo Search** | [Routine](https://github.com/realsirjoe/relinos_registry/blob/master/routines/duckduckgo_com_search.json) | [Extraction](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/duckduckgo_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=ebay.com&sz=64" width="20" height="20" align="absmiddle"> **eBay Search** | [Routine](https://github.com/realsirjoe/relinos_registry/blob/master/routines/ebay_com_search.json) | [Extraction](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/ebay_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=skyscanner.com&sz=64" width="20" height="20" align="absmiddle"> **Skyscanner Flight Search** | [Routine](https://github.com/realsirjoe/relinos_registry/blob/master/routines/skyscanner_com_flight_search.json) | [Extraction](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/skyscanner_com_flights.json)

You can then for example perform an easy Google search through **/do**

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

Once imported, routines can be executed through the API by your applications or LLMs.

## Building your own Routines

Relinos lets you combine browser interactions, pagination, caching, and structured extraction into a single JSON request, e.g:
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
    "pagination": ["//*[@id='pnnext']", "2"],
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


|Parameter   |Description                                                               |Example                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|url         | Downloads the url                                                        | `"https://example.com"`               |
|render      | Renders the site through a real browser                                  | `true` or `false`                   |
|cache       | Picks a cached result if it was less than the specified duration ago     | `"600s"` or `"60m"` or `"2h"` or `"7d"` or `"1y"` |
|debug       | Sends back x-debug-url header, visit the url to inspect and debug the interaction   | `true` or `false`    |
|includeMeta | Wraps meta information around the response                               | `true` or `false`                       |
|proxy       | Uses a supplied http, https or socks5 proxy, must include a scheme       | `http://127.0.0.1:1080` or `socks5://12.98.4.2:1988`          |
|format      | The output format                                                        | `"html"` or `"md"` or `"json"`            |
|actions     | A list of website interactions to perform, [see Interactions](#interactions) | `[["actionSelect", "//div[@id='email']", ""],["actionClick", "", ""]]`  |
|pagination  | Paginates over multiple pages. It is a json array containing the xpath for the next page url and the nr of pages to get | `["//a[@id='nextpage']", "2"]`  |
|extraction   | Specify a saved extraction's name or a full extraction. Requires format: "json". Don't forget to escape regexes to keep the JSON valid, [see Extraction](#extraction) to apply to the final html  | `"google_com_search_results"`           |

The response will return the final site after all interactions in the specified **format**. **includeMeta** will return JSON containing the final site inside the **data** key.

## Interactions

You can perform browser interactions, such as clicking or typing, through the `actions` parameter.
`actions` are a list of arrays, each containing the action name and 2 parameters

`actionClick` and `actionType` interact with the current selected element see actionSelect and actionFilter*


|Action                 |Param 1        |Param 2             |
|-----------------------|---------------|--------------------|
|actionSleep            |nr of seconds  |-                   |
|actionClick            |-              |-                   |
|actionType             |text           |-                   |
|actionKeyboardEnter    |-              |-                   |
|actionSelect           |xpath          |-                   |
|actionWaitForAndSelect |xpath          |max seconds to wait |
|actionFilterText       |text to contain|-                   |
|actionFilterAttribute  |attribute name | attribute value    |
|actionFilterIndex      |index          |-                   |
|actionExecuteScript    |javascript     |-                   |
|actionGoTo             |url            |-                   |


This example searches a site
```json
[
    ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
    ["actionType", "My Search Query", ""],
    ["actionKeyboardEnter", "", ""],
    ["actionSleep", "2", ""]
]
```

Actions are followed by a maximum of 2 arguments depending on the action.

## Saving Routines

To save and later reuse a routine, give it a name and parameters.

Start by changing **/get** to **POST /routines/your_routine_name**. 

To accept input, add a `params` object. Each key is the parameter name, and its value defines that parameter’s `description`, `default`, and/or `kind`

You can also add a `description` to the routine itself. 

If a routine already exists you must specify **overwrite=true** as query param to overwrite it

|Param Key      |Description                               |
|---------------|------------------------------------------|
|description    |                                          |
|default        | default value if parameter not present   |
|kind           | e.g. "int", "float", "str", "date"       |

You can then use the params on `url`, `actions` or `pagination` inside a string 

e.g. `"https://example.com?q=||search_term||"`

The param name is enclosed inside `||` you may specify a transform via `||paramName:someTransformation||`

Currently available transforms are `url_quote` and `url_query_quote`

It is recommended to use multiple routines for complex interactions, e.g. one for performing a search, one for buying a product, ... 

Here's a parametrized routine ready for saving
```json
{
    "description": "",
    "params": {
        "search_term": {
            "description": "",
            "default": ""
        },
        "max_pages": {
            "description": "",
            "default": "",
            "kind": "int"
        }
    },
    "url": "https://www.google.com",
    "render": true,
    "actions": [
        ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
        ["actionType", "||search_term||", ""],
        ["actionSleep", "1", ""],
        ["actionKeyboardEnter", "", ""],
        ["actionSleep", "2", ""]
    ],
    "pagination": ["//*[@id='pnnext']", "||max_pages||"],
    "extraction": ""
}
```

You can run routines with **/do**, in the JSON body use `name` for the routine, specify the required parameters inside `params` e.g. `"params": { "search_term": "How old is the earth" }`

You can delete via **DELETE /routines/your_routine_name**

You can also view all routines via **/routines** and search via **/routines?q=search_term**


## Extraction

One can transform any page's html into markdown, see `format`. 

Relinos also supports structured data extraction and validation with an extensible yet simple new format. 

XPathSchema structures data as a tree since most of the internet is represented in that form through html. The format is valid JSON and therefore easy to understand and reason about. 

An example XPathSchema looks like this

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
This is a schema for Google search.
It describes the data shape through parent child relationships. 
There is regular keys that describe the data itself and special keys starting with '$'. 

For example $xpath specifies what part of the html the data is in.
This way one could specify how to find each Google search result and inside each result how to find the title, url and description

The format itself therefore already shows the final format the extracted data will have.
It will create data like this

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

|Special key |Description                                                               |Example                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|$xpath      | xpath describing how to find the data                              | `"//div[@class='price']"`             |
|$pattern    | regex to match the data before $extract and $transform             | `"\\d[\\.\\d+]?"`                        |
|$required   | data must exist                                                          | `true` or `false`                       |
|$list       | Return all matching elements as a list instead of the first result.      | `true` or `false`                       |
|$format     | How to format the selected html, parent elements ignore format           | `"text"` or `"html"` or `"md"`            |
|$transform  | uses predefined functions to transform data                              | coming soon                         |
|$extract    | extracts string data with a regex by keeping the first capturing group, make sure to escape '\\'  | `"(\\d[\\.\\d+]?)US$"`                   |

You can add extractions if you want to reuse them later by reusing your **/get** or **/do** request body on **POST /extractions/your_extraction_name**, you can also add a `description` key to the body.  

You can remove them with **DELETE /extractions/your_extraction_name**

You can view all extractions with **/extractions** and search extractions with **/extractions?q=search_term**

## Error Handling

2xx — The request was successful.

4xx — The request failed due to a client-side error, such as invalid parameters or a missing resource.

5xx — The server encountered an error while processing the request.

Errors are returned in JSON, `detail` contains further information on the error

## Configuration

To change Relinos settings edit **~/.relinos/config**

Each setting follows the format `VARIABLE=VALUE`.

|variable            |Description                              |Example             |
|--------------------|-----------------------------------------|--------------------|
|PORT                | Port on which the api listens           | `1081`             |
|BROWSER_WORKER_PORT | Port on which the browser worker listens| `18765`            |
|BROWSER_POOL_SIZE   | Number of browser instances to run      | `2` or `10`        |

Restart Relinos for configuration changes to take effect.

## Older Relinos Versions

If you're upgrading from Relinos 0.3, 0.2 or earlier, routine parameters have been redesigned to be simpler, more powerful, and less prone to human errors. 
Run 

```source ~/.relinos/env/bin/activate; python3 -m relinos.migrate_routines``` 

to automatically update your existing routines inside `~/.relinos` to the newest version.

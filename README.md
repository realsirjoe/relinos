**Relinos** is a **browser** that does the browsing for you. 

It is a language agnostic tool for rendering, automating and extracting data on the web

![Relinos Demo](https://raw.githubusercontent.com/realsirjoe/designs/master/relinos_demo.gif)

# Getting Started

Relinos runs on Linux and OSX

**Install**
 
```
git clone https://github.com/realsirjoe/relinos
cd relinos
python3 relinos/install.py
```

**Start** 
```
bash relinos/start.sh
```

Once started you can render and interact with any site via **/get** 
The only required parameter is **url**

```
curl --request GET \
  --url http://0.0.0.0:8031/get \
  --header 'Content-Type: application/json' \
  --data '{
    "url": "https://stackoverflow.com",
    "render": true,
    "debug": true,
    "cache": "1d",
    "actions": [
        ["actionWaitForAndSelect", "//*[@data-gps-track='\''login.click'\'']", "5"],
        ["actionClick", "", ""],
        ["actionWaitForAndSelect", "//*[@id='\''email'\'']", "5"],
        ["actionType", "my email", ""],
        ["actionWaitForAndSelect", "//*[@id='\''password'\'']", "5"],
        ["actionType", "my password", ""],
        ["actionKeyboardEnter", "", ""],
        ["actionWaitForAndSelect", "//*[@class='\''bar-sm s-avatar--image js-avatar-me'\'']", "5"],
        ["actionClick", "", ""],
        ["actionSleep", "5", ""]
    ]
}'
```

|Parameter   |Description                                                               |Example                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|url         | Downloads the url                                                        | "https://example.com"               |
|render      | Renders the site through a real browser                                  | true or false                       |
|cache       | Picks a cached result if it was less than the specified duration ago     | "600s" or "60m" or "2h" or "7d" or "1y" |
|debug       | Sends back x-debug-url header, visit the url to inspect and debug the interaction   | true or false    |
|includeMeta | Wraps meta information around the response                               | true or false                       |
|format      | The output format                                                        | "html" or "md" or "json"            |
|actions     | A list of website interactions to perform, [see Automation](#automation) | [["actionSelect", "//div[@id='email']", ""],["actionClick", "", ""]]  |
|pagination  | Paginates over multiple pages. It is a tuple containing the xpath for the next page url and the nr of pages to get | ["//a[@id='nextpage']", 2]  |
|extraction   | Specify a saved extractions name or a full extraction. Requires format: "json". Dont forget to escape regexes to keep the json valid, see Extraction to apply to the final html  | "google_com_search_results"           |

The response will return the final site after all interactions in the specified **format**. **includeMeta** will return json containing the final site inside the **data** key.

# Shared Web Interactions

Import ready-to-use routines and extractions from the [Relinos Registry](https://github.com/realsirjoe/relinos_registry).

To import a routine or extraction, send the JSON file as the raw request body to the **/import** endpoint.

<a href="https://github.com/realsirjoe/relinos_registry">
<img src="https://www.google.com/s2/favicons?domain=google.com&sz=128" width="30" height="30" align="absmiddle">

<img src="https://www.google.com/s2/favicons?domain=maps.google.com&sz=128" width="30" height="30" align="absmiddle">

<img src="https://www.google.com/s2/favicons?domain=youtube.com&sz=128" width="30" height="30" align="absmiddle">

<img src="https://www.google.com/s2/favicons?domain=duckduckgo.com&sz=128" width="30" height="30" align="absmiddle">

<img src="https://www.google.com/s2/favicons?domain=skyscanner.com&sz=128" width="25" height="25" align="absmiddle">
</a>

# Browser Rendering

On the web many sites are driven by javascript, this requires rendering sites in a browser.
Relinos handles this under the hood using any Chromium browser like 'Google Chrome' if the **render** parameter is set to true
# Automation

One can send interactions like clicking or typing to the browser through the **actions** parameter. 
**actions** are a list of tuples, each containing the action name and 2 parameters

**actionClick** and **actionType** interact with the current selected elements see actionSelect and actionFilter*


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
```
[
    ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
    ["actionType", "My Search Query", ""],
    ["actionKeyboardEnter", "", ""],
    ["actionSleep", "2", ""]
]
```

Actions are followed by a maximum of 2 arguments depending on the action.

To save your routines you name and parametrize it. 

Simply start by changing **/get** to **POST /routines/your_routine_name**. 

Since you normally want your routine to take some input like a search term or credentials, **params** specifies where to put those values. You can also add a **description** to both the routine and each param. If a routine already exists you must specify **overwrite=true** as query param to overwrite it

|Param Key      |Description                               |
|---------------|------------------------------------------|
|name           | name of the parameter                    |
|description    |                                          |
|patches        | list of patches, see patch               |
|default        | default value if parameter not present   |
|kind           | e.g. "int", "float", "str", "date"       |

|Patch Key      |Description                                                                     |
|---------------|--------------------------------------------------------------------------------|
|keypath        |dot notation describing where to put parameter                                  |
|start          |Position in the string where insertion begins                                   |
|end            |Position in the string until where the original content is replaced             |
|transform      |Predefined function to apply to the parameter: url_quote or url_query_quote     |

It is recommended to use multiple routines for complex interactions, e.g. one for performing a search, one for buying a product, ... 

Here a parametrized routine ready for saving
```
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

You can run routines with **/do**, in the json body use **name** for the routine, specify the required parameters inside **params** e.g. "params": { "search_term": "How old is the earth" }

You can delete via **DELETE /routines/your_routine_name**

You can also view all routines via **/routines** and search via **/routines?q=search_term**


# Extraction

One can transform any pages html into markdown, see **format**. 

Relinos also support structured data extraction and validation with an extensible yet simple new format. 

XPathSchema structures data as a tree since most of the internet is represented in that form through html. The format is valid json and therefore easy to understand and reason about. 

An example XPathSchema looks like this

```
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
This is a schema for google search.
It describes the data shape through parent child relationships. 
There is normal keys that describe the data itself and special keys starting with '$'. 

For example $xpath specifies what part of the html the data is in.
This way one could specify how to find each google search result and inside each result how to find the title, url and description

The format itself therefore already shows the final format the extracted data will have.
It will create data like this

```
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
|$xpath      | xpath describing how to find the data                              | "//div[@class='price']"             |
|$pattern    | regex to match the data before $extract and $transform             | "\\d[\\.\\d+]?"                        |
|$required   | data must exist                                                          | true or false                       |
|$list       | Return all matching elements as a list instead of the first result.      | true or false                       |
|$format     | How to format the selected html, parent elements ignore format           | "text" or "html" or "md"            |
|$transform  | uses predefined functions to transform data                              | coming soon                         |
|$extract    | extracts string data with a regex by keeping the first capturing group, make sure to escape '\'  | "(\\d[\\.\\d+]?)US$"                   |

You can add extractions if you want to reuse them later by reusing your **/get** or **/do** request body on **POST /extractions/your_extraction_name**, you can also add a **description** key to the body.  

You can remove them with **DELETE /extractions/your_extraction_name**

You can view all extractions with **/extractions** and search extractions with **/extractions?q=search_term**

# Error Handling

2xx — The request was successful.

4xx — The request failed due to a client-side error, such as invalid parameters or a missing resource.

5xx — The server encountered an error while processing the request.

Errors are returned in json, **detail** contains further information on the error

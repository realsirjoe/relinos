<div align="center">

[English](README.md) · **简体中文** · [日本語](README_ja.md) · [Русский](README_ru.md) · [Português](README_pt.md)

# Relinos

### 一个可编程浏览器，可将网站转化为 API。

用于**渲染**和**交互**网站、控制**多个浏览器**并提取**结构化数据**的 REST API

</div>

![Relinos 演示](https://raw.githubusercontent.com/realsirjoe/designs/master/relinos_demo.gif)

# 快速开始

Relinos 可运行于 Linux 和 macOS。

**安装**
 
```bash
git clone https://github.com/realsirjoe/relinos
cd relinos
python3 relinos/install.py
```

**启动**
```bash
bash relinos/start.sh
```

启动后，你可以通过 **/get** 渲染并与任意网站交互。
唯一必需的参数是 `url`。

在终端中试运行以下示例，以确认一切正常。它会提取 DuckDuckGo 的搜索结果。

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

使用 `"format": "json"` 时，`extraction` 用于定义你想获取的 JSON 结构。你可以使用任意键名，例如 `results`、`title` 或 `description`。`$xpath` 属性指定在页面的哪个位置查找相应数据。

使用 `$list: true` 可提取多个匹配元素，而不只是第一个。你也可以嵌套对象，以提取更复杂的结构。
例如，每个 `result` 可包含 `url`、`title` 和 `description`。

[了解更多提取功能](#提取)

## 可共享的网站例程

你可以从 [Relinos Registry](https://github.com/realsirjoe/relinos_registry) 导入可直接使用的例程和提取配置。

只需复制一个 JSON 文件，并将其放入 POST **/import** API 端点的请求体中。

<img src="https://www.google.com/s2/favicons?domain=google.com&sz=64" width="20" height="20" align="absmiddle"> **Google 搜索** | [例程](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_search.json) | [提取配置](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=maps.google.com&sz=64" width="20" height="20" align="absmiddle"> **Google 地图搜索** | [例程](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_maps_search.json) | [提取配置](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_maps_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=youtube.com&sz=64" width="20" height="20" align="absmiddle"> **YouTube 搜索** | [例程](https://github.com/realsirjoe/relinos_registry/blob/master/routines/youtube_com_search.json) | [提取配置](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/youtube_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=duckduckgo.com&sz=64" width="20" height="20" align="absmiddle"> **DuckDuckGo 搜索** | [例程](https://github.com/realsirjoe/relinos_registry/blob/master/routines/duckduckgo_com_search.json) | [提取配置](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/duckduckgo_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=ebay.com&sz=64" width="20" height="20" align="absmiddle"> **eBay 搜索** | [例程](https://github.com/realsirjoe/relinos_registry/blob/master/routines/ebay_com_search.json) | [提取配置](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/ebay_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=skyscanner.com&sz=64" width="20" height="20" align="absmiddle"> **Skyscanner 航班搜索** | [例程](https://github.com/realsirjoe/relinos_registry/blob/master/routines/skyscanner_com_flight_search.json) | [提取配置](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/skyscanner_com_flights.json)

之后，你可以例如通过 **/do** 轻松执行 Google 搜索：

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

导入后，应用程序或 LLM 可通过 API 执行这些例程。

## 创建自己的例程

Relinos 可将浏览器交互、分页、缓存和结构化提取组合为单个 JSON 请求，例如：
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


|参数   |说明                                                               |示例                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|url         | 下载指定 URL                                                        | `"https://example.com"`               |
|render      | 通过真实浏览器渲染网站                                  | `true` 或 `false`                   |
|cache       | 若缓存结果距今未超过指定时长，则使用该缓存结果     | `"600s"`、`"60m"`、`"2h"`、`"7d"` 或 `"1y"` |
|debug       | 返回 `x-debug-url` 响应头；访问该 URL 可检查并调试交互   | `true` 或 `false`    |
|includeMeta | 在响应外层包装元数据                               | `true` 或 `false`                       |
|proxy       | 使用提供的 http、https 或 socks5 代理；必须包含协议方案       | `http://127.0.0.1:1080` 或 `socks5://12.98.4.2:1988`          |
|format      | 输出格式                                                        | `"html"`、`"md"` 或 `"json"`            |
|actions     | 要执行的网站交互列表，[参见交互](#交互) | `[["actionSelect", "//div[@id='email']", ""],["actionClick", "", ""]]`  |
|pagination  | 对多个页面进行分页。它是一个 JSON 数组，包含下一页 URL 的 XPath 和要获取的页数 | `["//a[@id='nextpage']", 2]`  |
|extraction   | 指定已保存提取配置的名称或完整的提取配置。需要 `format: "json"`。别忘了对正则表达式进行转义以保证 JSON 有效；[参见提取](#提取) 以应用于最终 HTML  | `"google_com_search_results"`           |

响应将以指定的 **format** 返回完成全部交互后的网站。**includeMeta** 会返回 JSON，其中最终网站内容位于 **data** 键中。

## 交互

你可以通过 `actions` 参数执行浏览器交互，例如点击或输入。
`actions` 是一个数组列表，每个数组都包含操作名称和 2 个参数。

`actionClick` 和 `actionType` 会与当前选中的元素交互；请参阅 actionSelect 和 actionFilter*。


|操作                 |参数 1        |参数 2             |
|-----------------------|---------------|--------------------|
|actionSleep            |秒数  |-                   |
|actionClick            |-              |-                   |
|actionType             |文本           |-                   |
|actionKeyboardEnter    |-              |-                   |
|actionSelect           |XPath          |-                   |
|actionWaitForAndSelect |XPath          |最长等待秒数 |
|actionFilterText       |要包含的文本|-                   |
|actionFilterAttribute  |属性名称 | 属性值    |
|actionFilterIndex      |索引          |-                   |
|actionExecuteScript    |JavaScript     |-                   |
|actionGoTo             |URL            |-                   |


以下示例会在网站中进行搜索：
```json
[
    ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
    ["actionType", "My Search Query", ""],
    ["actionKeyboardEnter", "", ""],
    ["actionSleep", "2", ""]
]
```

每个操作最多可带 2 个参数，具体取决于操作类型。

要保存例程以便后续复用，需要为其命名并进行参数化。

只需将 **/get** 改为 **POST /routines/your_routine_name**。

由于通常会希望例程接收搜索词或凭据等输入，`params` 用于指定这些值应填入的位置。你也可以为例程及每个参数添加 `description`。如果例程已存在，必须指定查询参数 **overwrite=true** 才能覆盖它。

|参数键      |说明                               |
|---------------|------------------------------------------|
|name           | 参数名称                    |
|description    |                                          |
|patches        | 补丁列表，参见 patch               |
|default        | 未提供参数时使用的默认值   |
|kind           | 例如 `"int"`、`"float"`、`"str"`、`"date"`       |

|补丁键      |说明                                                                     |
|---------------|--------------------------------------------------------------------------------|
|keypath        |使用点记法描述参数应填入的位置                                  |
|start          |字符串中开始插入的位置                                   |
|end            |原有内容被替换到的位置             |
|transform      |应用于参数的预定义函数：url_quote 或 url_query_quote     |

对于复杂交互，建议使用多个例程，例如一个用于搜索，另一个用于购买产品，等等。

以下是一个可直接保存的参数化例程：
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

你可以通过 **/do** 运行例程：在 JSON 请求体中使用 `name` 指定例程，并在 `params` 中提供所需参数，例如 `"params": { "search_term": "How old is the earth" }`。

可通过 **DELETE /routines/your_routine_name** 删除例程。

也可通过 **/routines** 查看所有例程，以及通过 **/routines?q=search_term** 搜索例程。


## 提取

可将任意页面的 HTML 转换为 Markdown，参见 `format`。

Relinos 还支持使用一种可扩展而简单的新格式进行结构化数据提取和验证。

XPathSchema 以树形结构组织数据，因为互联网中的大多数内容都以 HTML 的这种形式呈现。该格式是有效的 JSON，因此易于理解和推理。

一个 XPathSchema 示例如下：

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
这是一个用于 Google 搜索的模式。
它通过父子关系描述数据形状。
其中既有描述数据本身的普通键，也有以 `$` 开头的特殊键。

例如，`$xpath` 指定数据位于 HTML 的哪个部分。
这样就可以指定如何查找每一条 Google 搜索结果，以及如何在每条结果中查找标题、URL 和描述。

因此，该格式本身已展示了提取数据最终将呈现的格式。
它将生成如下数据：

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

|特殊键 |说明                                                               |示例                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|$xpath      | 描述如何查找数据的 XPath                              | `"//div[@class='price']"`             |
|$pattern    | 在 `$extract` 和 `$transform` 之前，用于匹配数据的正则表达式             | `"\\d[\\.\\d+]?"`                        |
|$required   | 数据必须存在                                                          | `true` 或 `false`                       |
|$list       | 以列表形式返回所有匹配元素，而不是第一个结果。      | `true` 或 `false`                       |
|$format     | 如何格式化选中的 HTML；父元素会忽略此格式           | `"text"`、`"html"` 或 `"md"`            |
|$transform  | 使用预定义函数转换数据                              | 即将推出                         |
|$extract    | 使用正则表达式提取字符串数据，保留第一个捕获组；请务必转义 `\\`  | `"(\\d[\\.\\d+]?)US$"`                   |

如果希望以后复用提取配置，可在 **POST /extractions/your_extraction_name** 上复用 **/get** 或 **/do** 的请求体；也可在请求体中添加 `description` 键。

可通过 **DELETE /extractions/your_extraction_name** 删除它们。

可通过 **/extractions** 查看所有提取配置，并通过 **/extractions?q=search_term** 搜索提取配置。

## 错误处理

2xx — 请求成功。

4xx — 请求因客户端错误而失败，例如参数无效或资源不存在。

5xx — 服务器在处理请求时发生错误。

错误以 JSON 形式返回，`detail` 包含错误的更多信息。

## 配置

如需修改 Relinos 设置，请编辑 **~/.relinos/config**。

每项设置均遵循 `VARIABLE=VALUE` 格式。

|变量            |说明                              |示例             |
|--------------------|-----------------------------------------|--------------------|
|PORT                | API 监听的端口           | `1081`             |
|BROWSER_WORKER_PORT | 浏览器工作进程监听的端口| `18765`            |
|BROWSER_POOL_SIZE   | 要运行的浏览器实例数量      | `2` 或 `10`        |

重启 Relinos 后，配置更改才会生效。

---

> 本文档由 LLM 翻译。请以 [README.md](README.md) 中的原始信息为准。

<div align="center">

[English](README.md) · [简体中文](README_zh.md) · **日本語** · [Русский](README_ru.md) · [Português](README_pt.md)

# Relinos

### サイトを API に変える、プログラム可能なブラウザ。

サイトの**レンダリング**と**操作**、**複数ブラウザ**の制御、**構造化データ**の抽出を行う REST API

</div>

![Relinos デモ](https://raw.githubusercontent.com/realsirjoe/designs/master/relinos_demo.gif)

# はじめに

Relinos は Linux と macOS で動作します。

**インストール**
 
```bash
git clone https://github.com/realsirjoe/relinos
cd relinos
python3 relinos/install.py
```

**起動**
```bash
bash relinos/start.sh
```

起動後は、**/get** を通じて任意のサイトをレンダリングし、操作できます。
必須パラメータは `url` のみです。

ターミナルで次の例を試し、すべて正しく動作することを確認してください。この例では DuckDuckGo の検索結果を抽出します。

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

`"format": "json"` を使用する場合、`extraction` で取得したい JSON の構造を定義します。`results`、`title`、`description` など、キー名は自由に指定できます。`$xpath` プロパティは、ページ上の対応するデータを取得する場所を指定します。

`$list: true` を使用すると、最初の要素だけでなく、一致する複数の要素を抽出できます。オブジェクトをネストして、より複雑な構造を抽出することもできます。
たとえば、各 `result` に `url`、`title`、`description` を含めることができます。

[抽出の詳細](#抽出)

## 共有サイトルーチン

[Relinos Registry](https://github.com/realsirjoe/relinos_registry) から、すぐに使えるルーチンと抽出設定をインポートできます。

JSON ファイルをコピーし、POST **/import** API エンドポイントのリクエストボディに入れるだけです。

<img src="https://www.google.com/s2/favicons?domain=google.com&sz=64" width="20" height="20" align="absmiddle"> **Google 検索** | [ルーチン](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_search.json) | [抽出設定](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=maps.google.com&sz=64" width="20" height="20" align="absmiddle"> **Google マップ検索** | [ルーチン](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_maps_search.json) | [抽出設定](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_maps_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=youtube.com&sz=64" width="20" height="20" align="absmiddle"> **YouTube 検索** | [ルーチン](https://github.com/realsirjoe/relinos_registry/blob/master/routines/youtube_com_search.json) | [抽出設定](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/youtube_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=duckduckgo.com&sz=64" width="20" height="20" align="absmiddle"> **DuckDuckGo 検索** | [ルーチン](https://github.com/realsirjoe/relinos_registry/blob/master/routines/duckduckgo_com_search.json) | [抽出設定](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/duckduckgo_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=ebay.com&sz=64" width="20" height="20" align="absmiddle"> **eBay 検索** | [ルーチン](https://github.com/realsirjoe/relinos_registry/blob/master/routines/ebay_com_search.json) | [抽出設定](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/ebay_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=skyscanner.com&sz=64" width="20" height="20" align="absmiddle"> **Skyscanner フライト検索** | [ルーチン](https://github.com/realsirjoe/relinos_registry/blob/master/routines/skyscanner_com_flight_search.json) | [抽出設定](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/skyscanner_com_flights.json)

たとえば、次のように **/do** から簡単に Google 検索を実行できます。

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

インポート後、アプリケーションまたは LLM から API を通じてルーチンを実行できます。

## 独自ルーチンの作成

Relinos では、ブラウザ操作、ページネーション、キャッシュ、構造化抽出を 1 つの JSON リクエストに組み合わせることができます。例：
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


|パラメータ   |説明                                                               |例                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|url         | URL をダウンロードする                                                        | `"https://example.com"`               |
|render      | 実際のブラウザでサイトをレンダリングする                                  | `true` または `false`                   |
|cache       | 指定期間内のキャッシュ結果があれば、それを使用する     | `"600s"`、`"60m"`、`"2h"`、`"7d"` または `"1y"` |
|debug       | `x-debug-url` ヘッダーを返す。この URL にアクセスすると、操作を確認・デバッグできる   | `true` または `false`    |
|includeMeta | レスポンスをメタ情報でラップする                               | `true` または `false`                       |
|proxy       | 指定した http、https、または socks5 プロキシを使用する。スキームを含める必要がある       | `http://127.0.0.1:1080` または `socks5://12.98.4.2:1988`          |
|format      | 出力形式                                                        | `"html"`、`"md"` または `"json"`            |
|actions     | 実行するウェブサイト操作のリスト。[操作](#操作)を参照 | `[["actionSelect", "//div[@id='email']", ""],["actionClick", "", ""]]`  |
|pagination  | 複数ページをページネーションする。次ページ URL の XPath と取得ページ数を含む JSON 配列 | `["//a[@id='nextpage']", 2]`  |
|extraction   | 保存済みの抽出設定名または完全な抽出設定を指定する。`format: "json"` が必要。JSON を有効に保つため、正規表現をエスケープすること。最終 HTML に適用する方法は[抽出](#抽出)を参照  | `"google_com_search_results"`           |

レスポンスでは、すべての操作が完了した後のサイトを、指定した **format** で返します。**includeMeta** は、最終サイトを **data** キー内に含む JSON を返します。

## 操作

クリックや入力などのブラウザ操作は、`actions` パラメータで実行できます。
`actions` は配列のリストで、各配列には操作名と 2 つのパラメータが含まれます。

`actionClick` と `actionType` は現在選択されている要素を操作します。actionSelect および actionFilter* を参照してください。


|操作                 |パラメータ 1        |パラメータ 2             |
|-----------------------|---------------|--------------------|
|actionSleep            |秒数  |-                   |
|actionClick            |-              |-                   |
|actionType             |テキスト           |-                   |
|actionKeyboardEnter    |-              |-                   |
|actionSelect           |XPath          |-                   |
|actionWaitForAndSelect |XPath          |最大待機秒数 |
|actionFilterText       |含めるテキスト|-                   |
|actionFilterAttribute  |属性名 | 属性値    |
|actionFilterIndex      |インデックス          |-                   |
|actionExecuteScript    |JavaScript     |-                   |
|actionGoTo             |URL            |-                   |


この例ではサイト内を検索します。
```json
[
    ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
    ["actionType", "My Search Query", ""],
    ["actionKeyboardEnter", "", ""],
    ["actionSleep", "2", ""]
]
```

アクションには、種類に応じて最大 2 個の引数を指定します。

ルーチンを保存して後で再利用するには、名前を付けてパラメータ化します。

まず、**/get** を **POST /routines/your_routine_name** に変更します。

通常は検索語や認証情報などの入力をルーチンに渡すため、`params` でそれらの値を設定する場所を指定します。ルーチンと各パラメータの両方に `description` を追加することもできます。ルーチンがすでに存在する場合、上書きするにはクエリパラメータとして **overwrite=true** を指定する必要があります。

|パラメータキー      |説明                               |
|---------------|------------------------------------------|
|name           | パラメータ名                    |
|description    |                                          |
|patches        | パッチのリスト。patch を参照               |
|default        | パラメータが存在しない場合のデフォルト値   |
|kind           | 例：`"int"`、`"float"`、`"str"`、`"date"`       |

|パッチキー      |説明                                                                     |
|---------------|--------------------------------------------------------------------------------|
|keypath        |パラメータを設定する場所を示すドット記法                                  |
|start          |文字列内で挿入を開始する位置                                   |
|end            |元の内容を置き換える終了位置             |
|transform      |パラメータに適用する事前定義関数：url_quote または url_query_quote     |

複雑な操作には、たとえば検索用と商品購入用に分けるなど、複数のルーチンを使用することをおすすめします。

以下は、保存可能なパラメータ化済みルーチンです。
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

ルーチンは **/do** で実行できます。JSON リクエストボディでは、`name` にルーチンを指定し、`params` 内に必要なパラメータを設定します。例：`"params": { "search_term": "How old is the earth" }`

削除するには **DELETE /routines/your_routine_name** を使用します。

すべてのルーチンは **/routines** で確認でき、**/routines?q=search_term** で検索できます。


## 抽出

任意のページの HTML を Markdown に変換できます。`format` を参照してください。

Relinos は、拡張可能かつシンプルな新しい形式による構造化データの抽出と検証にも対応しています。

インターネット上のコンテンツの多くは HTML を通じてこのような形式で表現されているため、XPathSchema はデータをツリーとして構造化します。この形式は有効な JSON であるため、理解しやすく扱いやすい形式です。

XPathSchema の例は次のとおりです。

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
これは Google 検索用のスキーマです。
親子関係によってデータの形状を表します。
データ自体を表す通常のキーと、`$` で始まる特別なキーがあります。

たとえば、`$xpath` はデータが HTML のどの部分にあるかを指定します。
このようにして、各 Google 検索結果の見つけ方と、各結果内でタイトル、URL、説明を見つける方法を指定できます。

したがって、この形式自体が抽出データの最終的な形式を示しています。
次のようなデータが生成されます。

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

|特別なキー |説明                                                               |例                              |
|------------|--------------------------------------------------------------------------|-------------------------------------|
|$xpath      | データの見つけ方を記述する XPath                              | `"//div[@class='price']"`             |
|$pattern    | `$extract` と `$transform` の前にデータを照合する正規表現             | `"\\d[\\.\\d+]?"`                        |
|$required   | データが必ず存在する                                                          | `true` または `false`                       |
|$list       | 最初の結果ではなく、一致するすべての要素をリストで返す。      | `true` または `false`                       |
|$format     | 選択した HTML の整形方法。親要素では `$format` は無視される           | `"text"`、`"html"` または `"md"`            |
|$transform  | 事前定義関数を用いてデータを変換する                              | 今後対応予定                         |
|$extract    | 正規表現で文字列データを抽出し、最初のキャプチャグループを保持する。`\\` を必ずエスケープすること  | `"(\\d[\\.\\d+]?)US$"`                   |

後で再利用したい抽出設定は、**POST /extractions/your_extraction_name** に **/get** または **/do** のリクエストボディを再利用して追加できます。リクエストボディに `description` キーを追加することもできます。

削除するには **DELETE /extractions/your_extraction_name** を使用します。

すべての抽出設定は **/extractions** で確認でき、**/extractions?q=search_term** で検索できます。

## エラー処理

2xx — リクエストは成功しました。

4xx — 無効なパラメータや存在しないリソースなど、クライアント側のエラーによりリクエストが失敗しました。

5xx — リクエストの処理中にサーバーでエラーが発生しました。

エラーは JSON で返され、`detail` にエラーの詳細情報が含まれます。

## 設定

Relinos の設定を変更するには、**~/.relinos/config** を編集します。

各設定は `VARIABLE=VALUE` 形式に従います。

|変数            |説明                              |例             |
|--------------------|-----------------------------------------|--------------------|
|PORT                | API がリッスンするポート           | `1081`             |
|BROWSER_WORKER_PORT | ブラウザワーカーがリッスンするポート| `18765`            |
|BROWSER_POOL_SIZE   | 実行するブラウザインスタンス数      | `2` または `10`        |

設定変更を有効にするには、Relinos を再起動してください。

---

> このドキュメントは LLM により翻訳されています。原文の情報については [README.md](README.md) を参照してください。

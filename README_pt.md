<div align="center">

[English](README.md) · [简体中文](README_zh.md) · [日本語](README_ja.md) · [Русский](README_ru.md) · **Português**

# Relinos

### Um navegador programável que transforma sites em APIs.

API REST para **renderizar** e **interagir** com sites, controlar **vários navegadores** e extrair **dados estruturados**

</div>

![Demonstração do Relinos](https://raw.githubusercontent.com/realsirjoe/designs/master/relinos_demo.gif)

# Primeiros passos

O Relinos funciona no Linux e no macOS.

**Instalação**
 
```bash
git clone https://github.com/realsirjoe/relinos
cd relinos
python3 relinos/install.py
```

**Iniciar**

```bash
bash relinos/start.sh
```

Depois de iniciado, você pode renderizar e interagir com qualquer site por meio de **/get**.
O único parâmetro obrigatório é `url`.

Experimente este exemplo no terminal para verificar se tudo está funcionando. Ele extrai os resultados de busca do DuckDuckGo.

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

Ao usar `"format": "json"`, uma `extraction` define a estrutura do JSON que você deseja obter. Você pode usar quaisquer nomes de chave, como `results`, `title` ou `description`. A propriedade `$xpath` especifica onde encontrar os dados correspondentes na página.

Use `$list: true` para extrair vários elementos correspondentes, em vez de apenas um. Também é possível aninhar objetos para extrair estruturas mais complexas.
Por exemplo, cada `result` pode conter uma `url`, um `title` e uma `description`.

[Mais sobre extrações](#extração)

## Rotinas compartilhadas para sites

Você pode importar rotinas e extrações prontas para uso a partir do [Registro do Relinos](https://github.com/realsirjoe/relinos_registry).

Basta copiar um arquivo JSON e colocá-lo no corpo da requisição da API **POST /import**.

<img src="https://www.google.com/s2/favicons?domain=google.com&sz=64" width="20" height="20" align="absmiddle"> **Busca Google** | [Rotina](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_search.json) | [Extração](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=maps.google.com&sz=64" width="20" height="20" align="absmiddle"> **Busca no Google Maps** | [Rotina](https://github.com/realsirjoe/relinos_registry/blob/master/routines/google_com_maps_search.json) | [Extração](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/google_com_maps_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=youtube.com&sz=64" width="20" height="20" align="absmiddle"> **Busca no YouTube** | [Rotina](https://github.com/realsirjoe/relinos_registry/blob/master/routines/youtube_com_search.json) | [Extração](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/youtube_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=duckduckgo.com&sz=64" width="20" height="20" align="absmiddle"> **Busca DuckDuckGo** | [Rotina](https://github.com/realsirjoe/relinos_registry/blob/master/routines/duckduckgo_com_search.json) | [Extração](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/duckduckgo_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=ebay.com&sz=64" width="20" height="20" align="absmiddle"> **Busca no eBay** | [Rotina](https://github.com/realsirjoe/relinos_registry/blob/master/routines/ebay_com_search.json) | [Extração](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/ebay_com_search_results.json)

<img src="https://www.google.com/s2/favicons?domain=skyscanner.com&sz=64" width="20" height="20" align="absmiddle"> **Busca de voos no Skyscanner** | [Rotina](https://github.com/realsirjoe/relinos_registry/blob/master/routines/skyscanner_com_flight_search.json) | [Extração](https://github.com/realsirjoe/relinos_registry/blob/master/extractions/skyscanner_com_flights.json)

Você pode, por exemplo, fazer uma busca simples no Google por meio de **/do**.

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

Depois de importadas, as rotinas podem ser executadas pela API por suas aplicações ou LLMs.

## Criando suas próprias rotinas

O Relinos permite combinar interações no navegador, paginação, cache e extração estruturada em uma única requisição JSON, por exemplo:

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

|Parâmetro   |Descrição                                                               |Exemplo                              |
|------------|------------------------------------------------------------------------|-------------------------------------|
|url         | Baixa a URL                                                            | `"https://example.com"`            |
|render      | Renderiza o site em um navegador real                                  | `true` ou `false`                   |
|cache       | Usa um resultado em cache se ele tiver sido obtido há menos tempo que a duração especificada | `"600s"` ou `"60m"` ou `"2h"` ou `"7d"` ou `"1y"` |
|debug       | Retorna o cabeçalho x-debug-url; acesse a URL para inspecionar e depurar a interação | `true` ou `false` |
|includeMeta | Inclui metainformações na resposta                                     | `true` ou `false`                   |
|proxy       | Usa um proxy HTTP, HTTPS ou SOCKS5 fornecido; deve incluir um esquema  | `http://127.0.0.1:1080` ou `socks5://12.98.4.2:1988` |
|format      | O formato da saída                                                     | `"html"` ou `"md"` ou `"json"` |
|actions     | Uma lista de interações a executar no site; [veja Interações](#interações) | `[["actionSelect", "//div[@id='email']", ""],["actionClick", "", ""]]` |
|pagination  | Percorre várias páginas. É um array JSON contendo o XPath da URL da próxima página e o número de páginas a obter | `["//a[@id='nextpage']", 2]` |
|extraction  | Especifique o nome de uma extração salva ou uma extração completa. Requer `format: "json"`. Não se esqueça de escapar regexes para manter o JSON válido; [veja Extração](#extração). Aplica-se ao HTML final | `"google_com_search_results"` |

A resposta retornará o site final, após todas as interações, no **format** especificado. **includeMeta** retornará um JSON contendo o site final dentro da chave **data**.

## Interações

Você pode realizar interações no navegador, como clicar ou digitar, por meio do parâmetro `actions`.
`actions` é uma lista de arrays, cada um contendo o nome da ação e 2 parâmetros.

`actionClick` e `actionType` interagem com o elemento atualmente selecionado; consulte `actionSelect` e `actionFilter*`.

|Ação                   |Parâm. 1                 |Parâm. 2                    |
|-----------------------|-------------------------|----------------------------|
|actionSleep            | número de segundos      | -                          |
|actionClick            | -                       | -                          |
|actionType             | texto                   | -                          |
|actionKeyboardEnter    | -                       | -                          |
|actionSelect           | xpath                   | -                          |
|actionWaitForAndSelect | xpath                   | máximo de segundos de espera |
|actionFilterText       | texto que deve conter   | -                          |
|actionFilterAttribute  | nome do atributo        | valor do atributo          |
|actionFilterIndex      | índice                  | -                          |
|actionExecuteScript    | javascript              | -                          |
|actionGoTo             | url                     | -                          |

Este exemplo faz uma busca em um site:

```json
[
    ["actionWaitForAndSelect", "//textarea[@name='q']", "1"],
    ["actionType", "My Search Query", ""],
    ["actionKeyboardEnter", "", ""],
    ["actionSleep", "2", ""]
]
```

As ações são seguidas de, no máximo, 2 argumentos, dependendo da ação.

Para salvar e reutilizar sua rotina posteriormente, atribua-lhe um nome e parâmetros.

Comece simplesmente alterando **/get** para **POST /routines/your_routine_name**.

Como normalmente você desejará que sua rotina receba alguma entrada, como um termo de busca ou credenciais, `params` especifica onde colocar esses valores. Você também pode adicionar uma `description` tanto à rotina quanto a cada parâmetro. Se uma rotina já existir, você deverá especificar **overwrite=true** como parâmetro de consulta para substituí-la.

|Chave de parâmetro |Descrição                                |
|-------------------|-----------------------------------------|
|name               | nome do parâmetro                       |
|description        |                                         |
|patches            | lista de patches; veja patch            |
|default            | valor padrão se o parâmetro não estiver presente |
|kind               | por exemplo, `"int"`, `"float"`, `"str"`, `"date"` |

|Chave de patch |Descrição                                                               |
|---------------|------------------------------------------------------------------------|
|keypath        | notação por pontos que descreve onde inserir o parâmetro               |
|start          | posição na string em que a inserção começa                             |
|end            | posição na string até a qual o conteúdo original é substituído         |
|transform      | função predefinida a aplicar ao parâmetro: `url_quote` ou `url_query_quote` |

Recomenda-se usar várias rotinas para interações complexas, por exemplo, uma para realizar uma busca e outra para comprar um produto.

Aqui está uma rotina parametrizada pronta para ser salva:

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

Você pode executar rotinas com **/do**. No corpo JSON, use `name` para a rotina e especifique os parâmetros necessários em `params`, por exemplo: `"params": { "search_term": "How old is the earth" }`.

Você pode excluí-las por meio de **DELETE /routines/your_routine_name**.

Também é possível visualizar todas as rotinas em **/routines** e pesquisá-las em **/routines?q=search_term**.

## Extração

É possível transformar o HTML de qualquer página em Markdown; consulte `format`.

O Relinos também oferece suporte à extração e à validação de dados estruturados por meio de um formato novo, simples e extensível.

O XPathSchema estrutura os dados como uma árvore, já que a maior parte da internet é representada dessa forma em HTML. O formato é JSON válido e, portanto, fácil de entender e analisar.

Um exemplo de XPathSchema é o seguinte:

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

Este é um esquema para uma busca do Google.
Ele descreve o formato dos dados por meio de relações entre elementos pai e filho.
Há chaves comuns que descrevem os próprios dados e chaves especiais que começam com `$`.

Por exemplo, `$xpath` especifica em qual parte do HTML estão os dados.
Assim, é possível especificar como encontrar cada resultado de busca do Google e, dentro de cada resultado, como encontrar o título, a URL e a descrição.

Portanto, o próprio formato já mostra a estrutura final dos dados extraídos.
Ele criará dados como estes:

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

|Chave especial |Descrição                                                               |Exemplo                              |
|---------------|------------------------------------------------------------------------|-------------------------------------|
|$xpath         | XPath que descreve como encontrar os dados                             | `"//div[@class='price']"`          |
|$pattern       | regex para corresponder aos dados antes de `$extract` e `$transform`   | `"\\d[\\.\\d+]?"`              |
|$required      | os dados devem existir                                                 | `true` ou `false`                   |
|$list          | Retorna todos os elementos correspondentes como uma lista, em vez do primeiro resultado | `true` ou `false` |
|$format        | Como formatar o HTML selecionado; elementos pai ignoram o formato      | `"text"` ou `"html"` ou `"md"`  |
|$transform     | usa funções predefinidas para transformar dados                        | em breve                            |
|$extract       | extrai dados de string com uma regex, mantendo o primeiro grupo de captura; não se esqueça de escapar `\\` | `"(\\d[\\.\\d+]?)US$"` |

Você pode adicionar extrações caso queira reutilizá-las mais tarde, reutilizando o corpo da sua requisição **/get** ou **/do** em **POST /extractions/your_extraction_name**. Também é possível adicionar uma chave `description` ao corpo.

Você pode removê-las com **DELETE /extractions/your_extraction_name**.

Você pode visualizar todas as extrações em **/extractions** e pesquisá-las em **/extractions?q=search_term**.

## Tratamento de erros

2xx — A requisição foi bem-sucedida.

4xx — A requisição falhou devido a um erro no cliente, como parâmetros inválidos ou um recurso ausente.

5xx — O servidor encontrou um erro ao processar a requisição.

Os erros são retornados em JSON; `detail` contém informações adicionais sobre o erro.

## Configuração

Para alterar as configurações do Relinos, edite **~/.relinos/config**.

Cada configuração segue o formato `VARIABLE=VALUE`.

|variável            |Descrição                                      |Exemplo             |
|--------------------|-----------------------------------------------|--------------------|
|PORT                | Porta em que a API escuta                     | `1081`             |
|BROWSER_WORKER_PORT | Porta em que o worker do navegador escuta     | `18765`            |
|BROWSER_POOL_SIZE   | Número de instâncias do navegador em execução | `2` ou `10`        |

Reinicie o Relinos para que as alterações de configuração entrem em vigor.

---

> **Aviso:** Esta tradução foi gerada com o auxílio de um LLM. Para consultar as informações de origem, veja o [README.md](README.md).

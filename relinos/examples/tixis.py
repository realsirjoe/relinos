# Checks a ticket site for availability and sends a telegram message
from typing import cast, Any
from time import sleep
import os

from relinos.config import serverName
from relinos.parse import JsonType

from curl_cffi import requests
from lxml import html

def sendTelegramMessage(text: str, chatID: str) -> None:
    botToken = os.getenv("BOT_TOKEN")
    if not botToken: 
        print(text)
        print("To send this message to your messenger set BOT_TOKEN env")
        return 
    endpoint = f"https://api.telegram.org/bot{botToken}/sendMessage"

    params = { "chat_id": chatID, "text": text, "parse_mode": "Markdown" }

    r = requests.get(endpoint, params=params)
    if not r.ok: print(r.text)
    r.raise_for_status() # type: ignore

def monitorTixis() -> None:
    url = "https://checkout.tix.is/is/buyingflow/tickets/21434/"

    reqData: JsonType = {
        "url": url,
        "render": True,
        "cache": "5m",
        "actions": [
            ["actionSleep", "2", ""],
            ["actionSelect", '//*[@class="plus-button primary-c-button"]', ""],
            ["actionClick", "", ""],
            ["actionSleep", "2", ""],
            ["actionSelect", '//*[@id="FindTickets"]', ""],
            ["actionClick", "", ""],
            ["actionSleep", "2", ""],
        ],
    }
    htmlSrc = requests.get(serverName + "/get", json=cast(dict[Any, Any], reqData)).text
    tree = html.fromstring(htmlSrc)
    selection: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath("//*[@id='TicketSelectTitle']") )
    if len(selection) == 0 or "unfortunately" not in selection[0].text_content().lower():
        message = f"tixis tickets available go to {url}"
        sendTelegramMessage(message, "11111")
    
if __name__ == "__main__":
    while True:
        monitorTixis()
        sleep(10)

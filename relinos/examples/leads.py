from typing import Any, cast
from urllib.parse import urlparse
import re

from relinos.config import dumpDirPath, serverName
from relinos.parse import JsonType
from relinos.examples.google import google

import requests
from lxml import html

def getCompanyContacts(searchTerm: str) -> tuple[list[str], list[str], str, str]:
    data, err = google(searchTerm, cache="1y")
    if err: raise err
    assert type(data) == dict
    results = cast(list[dict[str, Any]], data["results"])
    if not results or len(results) == 0:
        raise Exception(f"No valid entries found for {searchTerm}")

    # visit actual site
    website = results[0]["url"]
    reqData: JsonType = {
        "url": website,
        "render": True,
        "cache": "999y",
        "includeMeta": True,
    }
    resp = requests.get(serverName + "/get", json=reqData)
    resp.raise_for_status()
    data = resp.json()
    htmlSrc = data["data"]
    website = data["finalUrl"]
    host1 = urlparse(website).netloc.lower().replace("www.", "")

    tree = html.fromstring(htmlSrc)
    aTags: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath("//a"))
    links = []
    for aTag in aTags:
        url = aTag.get("href", "")
        host2 = urlparse(url).netloc.lower().replace("www.", "")
        title = aTag.text
        if not title: title = ""

        toSearch = title.replace("-", " ").replace(" ", "").lower() + url.replace("-", " ").replace(" ", "").lower()
        if host1 == host2:
            if "contact" in toSearch: links.append(url)

    links = list(set(links))
    contactURL = ""
    if len(links) > 0: contactURL = links[0]

    siteTels = []
    telLinks: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath('//a[starts-with(@href, "tel:")]'))
    for link in telLinks:
        href = link.get('href')
        siteTel = href.split('tel:')[-1].split('?')[0]

        # normalization
        if siteTel.startswith("00"): siteTel = "+" + siteTel[2:] 

        siteTels.append(siteTel) 

    siteTels = list(set(siteTels))

    emails = []
    emailLinks: list[html.HtmlElement] = cast(list[html.HtmlElement], tree.xpath('//a[starts-with(@href, "mailto:")]'))
    for link in emailLinks:
        href = link.get('href')
        # Extract the email by dropping the 'mailto:' prefix
        email = href.split('mailto:')[-1].split('?')[0]

        # Normalization
        email = email.removeprefix("http://")
        email = email.removeprefix("https://")

        emails.append(email)
    emails = list(set(emails))

    for link in aTags:
        emailRe = r"^[\w.-]+@[\w.-]+\.[A-Za-z]{2,}$"
        text = link.text_content().strip()
        match = re.fullmatch(emailRe, text)
        if match: emails.append(text)

    emails = list(set(emails))
    siteTels = list(set(siteTels))

    return emails, siteTels, website, contactURL, 

def getCompaniesContacts() -> None:
    searches = [
        "Ritz Carlton London",
        "Praxis im Tal Muenchen",
        "Narisawa Tokyo",
    ]

    for searchTerm in searches:
        print("Searching", searchTerm)
        emails, siteTels, website, contactURL = getCompanyContacts(searchTerm)
        print("Found:", emails, siteTels, website, contactURL)
        print("---")

if __name__ == "__main__":
    getCompaniesContacts()

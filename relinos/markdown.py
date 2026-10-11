import re
from dataclasses import dataclass, field

from lxml import html, etree
from markdownify import markdownify as md


DROP_TAGS = { "script", "style", "noscript", "template", "svg", "canvas", "iframe" }

@dataclass
class Node:
    tagID: int # deterministic for the same html file
    text: list[str] = field(default_factory=list)
    endText: str = field(default_factory=str)
    children: list["Node"] = field(default_factory=list)

def cleanText(text: str) -> str:
    """
    Normalize whitespace without destroying useful Markdown structure.
    """
    if not text: return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def removeTags(htmlStr: str, dropTags: list[str]) -> str:
    tree = html.fromstring(htmlStr)
    etree.strip_elements(tree, *dropTags, with_tail=False)
    return html.tostring(tree, encoding="unicode") or ""

def postprocessMarkdown(content: str, maxNewlines: int = 3) -> tuple[str, int]:
    """
    Light cleanup after rendering.

    Important:
    This avoids deleting normal brace blocks like: 
    {
      text
    }

    ( see at brace markdown )

    It only removes obvious giant JSON-ish lines.
    """
    originalLength = len(content)

    # Remove JSON blobs (common in SPAs like LinkedIn, Facebook, etc.)
    # These are often embedded as `{"key":"value",...}` and can be massive
    # Match JSON objects/arrays that are at least 100 chars long
    # This catches SPA state/config data without removing small inline JSON
    content = re.sub(r"`\{[\"'\w].*?\}`", "", content, flags=re.DOTALL) # Remove JSON in code blocks

    content = re.sub(r"\{\"\$type\":[^}]{100,}\}", "", content) # Remove JSON with $type fields (common pattern)
    content = re.sub(r"\{\"[^\"]{5,}\":\{[^}]{100,}\}", "", content) # Remove nested JSON objects

    # Compress consecutive newlines (4+ newlines become maxNewlines)
    content = re.sub(r"\n{4,}", "\n" * maxNewlines, content)

    filteredLines = []
    lines = content.split('\n')
    for line in lines:
        stripped = line.strip()

        # Do NOT remove ordinary brace hierarchy lines.
        looksLikeJSON = len(stripped) > 100 and stripped.startswith(('{"', "[{", '["'))
        if looksLikeJSON: continue
        filteredLines.append(line)

    content = "\n".join(filteredLines).strip()
    charsFiltered = originalLength - len(content)

    return content, charsFiltered

def hasElementChildren(el: html.HtmlElement) -> bool:
    return any(isinstance(child.tag, str) for child in el)

def markdownFragment(el: html.HtmlElement, extractImages: bool = True) -> str:
    """
    Convert a small HTML element to Markdown.

    This is mostly used for leaves such as:
    <span>€129</span>
    <a href="...">Buy</a>
    <img src="..." alt="...">
    <h2>Product title</h2>
    """
    # tail should not be part of element markdown otherwise duplicate data
    htmlFragment = html.tostring(el, encoding="unicode")

    keepInlineImagesIn = [
        "td","th", "h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "span", "a",
    ]

    content = md(
        htmlFragment,
        heading_style="ATX",
        strip=["script", "style"],
        bullets="-",
        code_language="",
        escape_asterisks=False,
        escape_underscores=False,
        escape_misc=False,
        autolinks=False,
        default_title=False,
        keep_inline_images_in=keepInlineImagesIn if extractImages else [],
    )
    el.tail = ""

    return cleanText(content)

def buildTree(el: html.HtmlElement, extractImages: bool = True) -> Node|None:
    """
    Build a semantic-ish tree from HTML.

    Tags are NOT preserved.
    Only text/Markdown leaves and child relationships are preserved.
    """
    if not isinstance(el.tag, str):
        return None

    tag = el.tag.lower()
    tagID = el.attrib[tagIDAttribute]

    if tag in DROP_TAGS: return None

    # Leaf element: render directly as Markdown.
    if not hasElementChildren(el):
        rendered = markdownFragment(el, extractImages=extractImages)

        if not rendered: return None
        return Node(tagID=tagID, text=[rendered])
        
    # Parent element.
    node = Node(tagID=tagID)

    if el.text and el.text.strip():
        node.text.append(cleanText(el.text))

    for child in el:
        child_node = buildTree(child, extractImages=extractImages)

        if child_node:
            node.children.append(child_node)

        if child.tail and child.tail.strip():
            node.text.append(cleanText(child.tail))

    if not node.text and not node.children:
        return None

    # for nested links
    if el.tag == "a" and el.get("href"):
        node.text = [f"["] + node.text
        node.endText = f"]({el.get('href')})"

    return node

def indentLine(line: str, depth: int) -> str:
    return "  " * depth + line

def renderNode(node: Node, depth: int = 0, collapse: bool = True, includeTagID: bool = False) -> list[str]:
    """
    Render simplified Node tree to anonymous brace hierarchy.
    """
    lines: list[str] = []

    shouldWrap = len(node.children) > 1 or node.text or not collapse

    if shouldWrap:
        lines.append(indentLine("{", depth))
        depth += 1

    for text in node.text:
        text = cleanText(text).replace("{", "INLINE_BRACKET_OPEN").replace("}", "INLINE_BRACKET_CLOSE")

        if not text:
            continue

        for line in text.splitlines():
            if line.strip():
                lines.append(indentLine(line, depth))

    for child in node.children:
        lines.extend(renderNode(child, depth, collapse=collapse, includeTagID=includeTagID))

    if node.endText:
        lines.append(indentLine(node.endText, depth))
    if shouldWrap:
        if includeTagID and " ".join(node.text).strip() or node.endText.strip(): 
            lines.append(indentLine("UNIQUEID" + str(node.tagID), depth))
        depth -= 1
        lines.append(indentLine("}", depth))

    return lines

tagIDAttribute = "_crawltagid_"

def htmlToBraceMarkdown(htmlStr: str, extractImages: bool = True, collapse: bool = True, includeTagID: bool = True) -> str:
    """
    Convert HTML to Markdown-like text with collapsed hierarchy.

    Output example:

    {
      # Product title
      {
        €129
        ![image](image.jpg)
      }
    }

    No HTML tags are kept.
    Empty/single-child wrapper layers are collapsed.
    """
    if not htmlStr or not htmlStr.strip(): return ""

    root = html.fromstring(htmlStr)
    # Changes dom to assign an id to every tag
    # Not optimal since it changes dom/html
    # .iter() is deterministic for the same html
    for i, node in enumerate(root.iter()): 
        if not isinstance(node.tag, str): continue
        node.set(tagIDAttribute, str(i))

    tree = buildTree(root, extractImages=extractImages)

    if not tree: return ""

    lines = renderNode(tree, collapse=collapse, includeTagID=includeTagID)
    content = "\n".join(lines)

    content = re.sub(r"\n{3,}", "\n\n", content)
    content = content.strip()

    content, _ = postprocessMarkdown(content)

    return content

def htmlToMarkdown(htmlStr: str, extractImages: bool = True) -> str:
    """
    'td', 'th', and headings are the only elements where markdownify sets the _inline context,
    which causes img elements to be stripped to just alt text when keep_inline_images_in=[]
    """
    
    # Remove tags that usually contain noise or non-visible content.
    htmlStr = removeTags(htmlStr, ["script", "style"])

    if not extractImages: htmlStr = removeTags(htmlStr, ["img"])

    keepInlineImagesIn = ['td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'] if extractImages else []
    content = md(
        htmlStr,
        heading_style='ATX',  # Use # style headings
        strip=['script', 'style'],  # Remove these tags
        bullets='-',  # Use - for unordered lists
        code_language='',  # Don't add language to code blocks
        escape_asterisks=False,  # Don't escape asterisks (cleaner output)
        escape_underscores=False,  # Don't escape underscores (cleaner output)
        escape_misc=False,  # Don't escape other characters (cleaner output)
        autolinks=False,  # Don't convert URLs to <> format
        default_title=False,  # Don't add default title attributes
        keep_inline_images_in=keepInlineImagesIn,  # Include image src URLs when extractImages=True
    )

    # Minimal cleanup - markdownify already does most of the work
    content = re.sub(r'%[0-9A-Fa-f]{2}', '', content)  # Remove any remaining URL encoding
    content, chars_filtered = postprocessMarkdown(content)

    return content

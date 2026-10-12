from bs4 import BeautifulSoup
from backend.safety import sanitize_html, markdown_html, CSP


def test_active_html_and_navigation_removed():
    raw = '<html><head><style>@import "https://evil.invalid/a.css"; p {color:red}</style></head><body><script>alert(1)</script><iframe src="https://evil.invalid"></iframe><form><input></form><a href="javascript:alert(1)" onclick="alert(2)">safe text</a><p>Useful content [S1]</p></body></html>'
    clean = sanitize_html(raw)
    soup=BeautifulSoup(clean,'html.parser')
    assert not soup.find(['script','iframe','form','input'])
    assert not soup.find('a').has_attr('href')
    assert not soup.find('a').has_attr('onclick')
    assert '@import' not in clean
    assert 'Useful content' in clean
    assert len(soup.find_all('html')) == 1
    assert soup.find('meta',attrs={'http-equiv':'Content-Security-Policy'})['content'] == CSP


def test_markdown_does_not_execute_raw_html():
    rendered=markdown_html('<img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1))')
    soup=BeautifulSoup(rendered,'html.parser')
    assert not soup.find('img')
    assert all(not a.get('href','').startswith('javascript:') for a in soup.find_all('a'))

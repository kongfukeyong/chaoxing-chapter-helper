"""Verify Chaoxing's visual choice controls fill the hidden answer field."""

import tempfile
import threading
from pathlib import Path

import app
from selenium import webdriver
from selenium.webdriver.edge.service import Service


HTML = '''<script>
function choose(el) {
 const group=el.parentNode, target=el.querySelector('span');
 if (el.getAttribute('qtype') !== '1')
   group.querySelectorAll('span').forEach(x=>x.classList.remove('check_answer'));
 target.classList.toggle('check_answer');
 document.querySelector('#answer1').value=[...group.querySelectorAll('.check_answer')]
   .map(x=>x.getAttribute('data')).join('');
}
</script>
<div class="TiMu"><div class="Zy_TItle">Pick B</div>
<ul class="Zy_ulTop"><li qtype="0" onclick="choose(this)"><span class="num_option" data="A"></span><a>A option</a></li>
<li qtype="0" onclick="choose(this)"><span class="num_option" data="B"></span><a>B option</a></li></ul>
<input type="hidden" id="answer1"></div>'''

with tempfile.TemporaryDirectory() as temp:
    page = Path(temp) / "page.html"
    page.write_text(HTML, encoding="utf-8")
    options = webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(service=Service(str(Path(__file__).parent / "drivers/msedgedriver.exe")), options=options)
    try:
        driver.get(page.as_uri())
        groups = app.read_groups(driver, {}, print, threading.Event())
        assert len(groups) == 1 and groups[0][1][0].choice_style == "chaoxing"
        assert app.fill_answer(driver, groups[0][1][0], "B")
        assert driver.find_element("id", "answer1").get_attribute("value") == "B"
        print("Visual choice fill passed")
    finally:
        driver.quit()

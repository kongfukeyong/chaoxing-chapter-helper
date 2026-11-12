"""Local nested-frame and answer-filling smoke test."""

import os
import tempfile
import threading
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import app
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / "work.html").write_text('''<!doctype html><html><body>
    <div class="TiMu"><div class="Zy_TItle">Which number is two?</div>
      <ul class="Zy_ulTop"><li><input type="radio" name="q1" value="0">A. one</li>
      <li><input type="radio" name="q1" value="1">B. two</li></ul></div>
    <div class="TiMu"><div class="Zy_TItle">Name a primary color</div>
      <textarea></textarea></div>
    <div class="ZY_sub"><a class="btnSubmit" onclick="window.top.document.querySelector('#workpop').style.display='block'">Submit</a></div>
    </body></html>''', encoding="utf-8")
    (root / "index.html").write_text('<iframe src="work.html"></iframe>', encoding="utf-8")
    (root / "cards.html").write_text('<iframe src="index.html"></iframe>', encoding="utf-8")
    (root / "page.html").write_text('''<div id="workpop" style="display:block">确认提交？
      <a onclick="document.body.dataset.submitted='yes';document.querySelector('#workpop').style.display='none'">提交</a></div>
      <iframe src="cards.html"></iframe>''', encoding="utf-8")
    options = webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(service=Service(str(Path(__file__).resolve().parent / "drivers" / "msedgedriver.exe")), options=options)
    try:
        driver.get((root / "page.html").as_uri())
        groups = app.read_groups(driver, {}, print, threading.Event())
        assert [len(items) for _, items in groups] == [1, 1], groups
        assert groups[0][1][0].options[1][1] == "B. two"
        result = app.fill_answer(driver, groups[0][1][0], "B")
        print("choice result", result, [(x[0], x[2].is_selected()) for x in groups[0][1][0].options], flush=True)
        assert result
        assert app.fill_answer(driver, groups[1][1][0], "red")
        assert groups[0][1][0].options[1][2].is_selected()
        assert groups[1][1][0].element.get_attribute("value") == "red"
        assert app.submit_homework(driver, print, threading.Event())
        assert driver.find_element(By.TAG_NAME, "body").get_attribute("data-submitted") == "yes"
        print("Chaoxing nested-frame smoke test passed")
    finally:
        driver.quit()

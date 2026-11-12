"""Verify whole-catalog navigation, video discovery, and stop behavior."""

import tempfile
import threading
from pathlib import Path

import directory
from selenium import webdriver
from selenium.webdriver.edge.service import Service


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / "cards1.html").write_text('<div class="ans-attach-ct videoContainer"><iframe src="video.html"></iframe></div>', encoding="utf-8")
    (root / "cards2.html").write_text('<div class="TiMu">Question</div>', encoding="utf-8")
    (root / "video.html").write_text('<video></video>', encoding="utf-8")
    (root / "page.html").write_text('''<div class="posCatalog_name" title="Video" onclick="document.querySelector('iframe').src='cards1.html'">Video</div>
      <div class="posCatalog_name" title="Work" onclick="document.querySelector('iframe').src='cards2.html'">Work</div>
      <iframe src="cards1.html"></iframe>''', encoding="utf-8")
    options = webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(service=Service(str(Path(__file__).parent / "drivers" / "msedgedriver.exe")), options=options)
    played, solved = [], []
    old_play = directory.play_video
    try:
        driver.get((root / "page.html").as_uri())
        assert len(directory.catalog_items(driver)) == 2
        directory.play_video = lambda d, stop, log, index: played.append(index) or True
        def solve(d, config, stop, log):
            solved.append(d.find_elements("css selector", "iframe")[0].get_attribute("src"))
            if len(solved) == 1:
                raise RuntimeError("simulated page failure")
            return True
        directory.process_directory(driver, {}, threading.Event(), lambda _: None, solve)
        assert played == [0] and len(solved) == 2
        assert "cards2.html" in solved[1]
        print("Directory traversal smoke test passed")
    finally:
        directory.play_video = old_play
        driver.quit()

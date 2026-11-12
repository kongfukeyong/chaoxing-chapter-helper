"""Verify whole-catalog navigation, video discovery, and stop behavior."""

import tempfile
import threading
from pathlib import Path

import directory
from chaoxing import enter_homework_frame
from selenium import webdriver
from selenium.webdriver.edge.service import Service


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / "cards1.html").write_text('<div class="ans-attach-ct videoContainer"><iframe src="video.html"></iframe></div><div class="ans-attach-ct"><iframe jobid="work-mixed" src="work.html"></iframe></div>', encoding="utf-8")
    (root / "cards2.html").write_text('<div class="ans-attach-ct"><iframe jobid="work-test" src="work.html"></iframe></div>', encoding="utf-8")
    (root / "cards3.html").write_text('<div class="ans-attach-ct ans-job-finished"><iframe jobid="work-done" src="work.html"></iframe></div>', encoding="utf-8")
    (root / "work.html").write_text('<div class="TiMu">Question</div>', encoding="utf-8")
    (root / "video.html").write_text('<video></video>', encoding="utf-8")
    (root / "page.html").write_text('''<div class="posCatalog_select"><div class="posCatalog_name" title="Video" onclick="document.querySelector('iframe').src='cards1.html'">Video</div></div>
      <div class="posCatalog_select"><div class="posCatalog_name" title="Work" onclick="document.querySelector('iframe').src='cards2.html'">Work</div></div>
      <div class="posCatalog_select"><div class="posCatalog_name" title="Done work" onclick="document.querySelector('iframe').src='cards3.html'">Done work</div></div>
      <div class="posCatalog_select"><div class="posCatalog_name" title="Done page" onclick="document.querySelector('iframe').src='cards3.html'">Done page</div><span class="icon_Completed"></span></div>
      <iframe src="cards1.html"></iframe>''', encoding="utf-8")
    options = webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    driver = webdriver.Edge(service=Service(str(Path(__file__).parent / "drivers" / "msedgedriver.exe")), options=options)
    played, solved, sequence = [], [], []
    old_play = directory.play_video
    try:
        driver.get((root / "page.html").as_uri())
        assert len(directory.catalog_items(driver)) == 4
        directory.play_video = lambda d, stop, log, index: played.append(index) or sequence.append("video") or True
        def solve(d, config, stop, log):
            solved.append(d.find_elements("css selector", "iframe")[0].get_attribute("src"))
            assert enter_homework_frame(d)
            d.switch_to.default_content()
            sequence.append("work")
            return True
        directory.process_directory(driver, {}, threading.Event(), lambda _: None, solve)
        assert played == [0] and len(solved) == 2
        assert "cards1.html" in solved[0] and "cards2.html" in solved[1]
        assert sequence[:2] == ["video", "work"]
        print("Directory traversal smoke test passed")
    finally:
        directory.play_video = old_play
        driver.quit()

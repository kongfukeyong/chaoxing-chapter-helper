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
    (root / "cards1.html").write_text('<div class="ans-attach-ct videoContainer"><iframe src="video.html"></iframe></div><div class="ans-attach-ct"><iframe src="work.html"></iframe></div>', encoding="utf-8")
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
        def play(d, stop, log, index):
            played.append(index)
            sequence.append("video")
            d.switch_to.default_content()
            d.switch_to.frame(d.find_element("css selector", "iframe"))
            d.execute_script("document.querySelector('.videoContainer').classList.add('ans-job-finished')")
            d.switch_to.default_content()
            return True
        directory.play_video = play
        def solve(d, config, stop, log):
            solved.append(d.find_elements("css selector", "iframe")[0].get_attribute("src"))
            assert enter_homework_frame(d)
            d.switch_to.default_content()
            d.switch_to.frame(d.find_element("css selector", "iframe"))
            d.execute_script("document.querySelector('.ans-attach-ct:not(.videoContainer)').classList.add('ans-job-finished')")
            d.switch_to.default_content()
            sequence.append("work")
            return True
        assert directory.process_directory(driver, {}, threading.Event(), lambda _: None, solve)
        assert played == [0] and len(solved) == 2
        assert "cards1.html" in solved[0] and "cards2.html" in solved[1]
        assert sequence[:2] == ["video", "work"]
        driver.get((root / "page.html").as_uri())
        failures = []
        assert not directory.process_directory(driver, {}, threading.Event(), failures.append,
                                                lambda d, config, stop, log: False)
        assert any("停在当前节" in message for message in failures)
        assert any("目录未完成" in message for message in failures)
        assert not any("打开：Work" in message for message in failures)
        (root / "tab_video.html").write_text('<div class="ans-attach-ct videoContainer"><iframe src="video.html"></iframe></div>', encoding="utf-8")
        (root / "tab_work.html").write_text('<div class="ans-attach-ct"><iframe src="work.html"></iframe></div>', encoding="utf-8")
        (root / "tabpage.html").write_text('''<div class="posCatalog_select"><div class="posCatalog_name" title="One section" onclick="void(0)">One section</div></div>
          <div id="prev_tab"><ul class="prev_ul">
          <li onclick="document.querySelector('iframe').src='tab_video.html'">Video</li>
          <li onclick="document.querySelector('iframe').src='tab_work.html'">Quiz</li>
          </ul></div><iframe src="tab_video.html"></iframe>''', encoding="utf-8")
        played.clear()
        solved.clear()
        sequence.clear()
        driver.get((root / "tabpage.html").as_uri())
        assert directory.process_directory(driver, {}, threading.Event(), lambda _: None, solve)
        assert played == [0] and len(solved) == 1
        assert sequence == ["video", "work"]
        print("Directory traversal smoke test passed")
    finally:
        directory.play_video = old_play
        driver.quit()

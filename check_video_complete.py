"""A video already accepted by the platform must not block the next card."""

import tempfile
import threading
import time
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import directory
from selenium import webdriver
from selenium.webdriver.edge.service import Service


with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    (root / "video.html").write_text('''<video></video>
      <button class="vjs-big-play-button" onclick="document.body.dataset.clicked='yes'">Play</button>''', encoding="utf-8")
    (root / "page.html").write_text('''<div class="ans-attach-ct videoContainer">
      <iframe src="video.html"></iframe></div>
      <script>setTimeout(()=>document.querySelector('.videoContainer')
        .classList.add('ans-job-finished'),1200)</script>''', encoding="utf-8")
    options = webdriver.EdgeOptions()
    options.add_argument("--headless=new")
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    driver = webdriver.Edge(service=Service(str(Path(__file__).parent / "drivers/msedgedriver.exe")), options=options)
    try:
        driver.get(f"http://127.0.0.1:{server.server_port}/page.html")
        started = time.monotonic()
        assert directory.play_video(driver, threading.Event(), lambda _: None)
        assert time.monotonic() - started < 18
        driver.switch_to.frame(driver.find_element("css selector", "iframe"))
        assert driver.find_element("tag name", "body").get_attribute("data-clicked") == "yes"
        print("Video completion transition passed")
    finally:
        driver.quit()
        server.shutdown()

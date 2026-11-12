"""Walk the visible Chaoxing course catalog and its page tasks."""

import time

from selenium.webdriver.common.by import By


CATALOG = ".posCatalog_name[onclick]"


def catalog_items(driver):
    driver.switch_to.default_content()
    return [(item.get_attribute("onclick"), item.get_attribute("title") or item.text.strip())
            for item in driver.find_elements(By.CSS_SELECTOR, CATALOG)
            if item.get_attribute("onclick")]


def visit_frames(driver, callback, depth=0):
    if callback(driver):
        return True
    if depth >= 5:
        return False
    for frame in driver.find_elements(By.CSS_SELECTOR, "iframe, frame"):
        try:
            driver.switch_to.frame(frame)
            if visit_frames(driver, callback, depth + 1):
                return True
        except Exception:
            pass
        driver.switch_to.parent_frame()
    return False


def play_video(driver, stopped, log, card_index=0):
    driver.switch_to.default_content()
    def find_cards(d):
        return bool(d.find_elements(By.CSS_SELECTOR, ".ans-attach-ct.videoContainer"))
    if not visit_frames(driver, find_cards):
        driver.switch_to.default_content()
        return False
    cards = driver.find_elements(By.CSS_SELECTOR, ".ans-attach-ct.videoContainer")
    if card_index >= len(cards):
        driver.switch_to.default_content()
        return False
    frames = cards[card_index].find_elements(By.CSS_SELECTOR, "iframe")
    if not frames:
        driver.switch_to.default_content()
        return False
    driver.switch_to.frame(frames[0])
    def find_video(d):
        videos = d.find_elements(By.CSS_SELECTOR, "video")
        if not videos:
            return False
        video = videos[0]
        d.execute_script("arguments[0].scrollIntoView({block:'center'});", video)
        try:
            d.execute_script("arguments[0].play();", video)
        except Exception:
            buttons = d.find_elements(By.CSS_SELECTOR, ".vjs-big-play-button, .vjs-play-control")
            if buttons:
                buttons[0].click()
        return True
    if not visit_frames(driver, find_video):
        driver.switch_to.default_content()
        return False
    log("视频已开始播放；等待实际播放完成。")
    start = time.monotonic()
    last_progress = start
    last_time = -1
    while not stopped.is_set() and time.monotonic() - start < 4 * 3600:
        state = driver.execute_script("""const v=document.querySelector('video');
            return v ? {ended:v.ended,paused:v.paused,time:v.currentTime,
                        duration:v.duration} : null;""")
        if not state:
            break
        if state["ended"] or (state["duration"] and state["time"] >= state["duration"] - 1):
            log("视频播放结束。")
            driver.switch_to.default_content()
            return True
        if state["time"] > last_time + 0.5:
            last_time = state["time"]
            last_progress = time.monotonic()
        elif time.monotonic() - last_progress > 40:
            log("视频播放进度持续未变化，请在浏览器检查播放限制。")
            break
        if state["paused"]:
            buttons = driver.find_elements(By.CSS_SELECTOR, ".vjs-big-play-button, .vjs-play-control")
            try:
                if buttons:
                    buttons[0].click()
                else:
                    driver.execute_script("document.querySelector('video').play();")
            except Exception:
                pass
        for _ in range(10):
            if stopped.is_set():
                break
            time.sleep(1)
    driver.switch_to.default_content()
    return False


def process_directory(driver, config, stopped, log, solve_page):
    items = catalog_items(driver)
    if not items:
        raise RuntimeError("当前页未找到超星课程目录，请先打开课程的学生学习页面。")
    log(f"目录共有 {len(items)} 个页面，开始逐页处理。")
    done = 0
    for index, (onclick, title) in enumerate(items, 1):
        if stopped.is_set():
            break
        driver.switch_to.default_content()
        candidates = driver.find_elements(By.CSS_SELECTOR, CATALOG)
        item = next((x for x in candidates if x.get_attribute("onclick") == onclick), None)
        if item is None:
            log(f"[{index}/{len(items)}] 目录项已变化，跳过：{title}")
            continue
        log(f"[{index}/{len(items)}] 打开：{title}")
        try:
            item.click()
            time.sleep(2)
            # The card iframe contains one or more task cards.
            driver.switch_to.default_content()
            def unfinished_videos(d):
                cards = d.find_elements(By.CSS_SELECTOR,
                    ".ans-attach-ct.videoContainer:not(.ans-job-finished)")
                return bool(cards)
            if visit_frames(driver, unfinished_videos):
                cards = driver.find_elements(By.CSS_SELECTOR, ".ans-attach-ct.videoContainer")
                pending = [n for n, card in enumerate(cards)
                           if "ans-job-finished" not in (card.get_attribute("class") or "")]
                driver.switch_to.default_content()
                for number, card_index in enumerate(pending, 1):
                    if stopped.is_set():
                        break
                    log(f"播放视频 {number}/{len(pending)}")
                    if not play_video(driver, stopped, log, card_index):
                        log("视频未能播放完成，继续处理当前页其他任务。")
            driver.switch_to.default_content()
            if solve_page(driver, config, stopped, log):
                done += 1
        except Exception as exc:
            log(f"[{index}/{len(items)}] 处理失败：{title}；{str(exc)[:120]}")
            driver.switch_to.default_content()
    driver.switch_to.default_content()
    log(f"目录处理结束：共浏览 {len(items)} 页，成功处理作业 {done} 页。")

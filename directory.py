"""Walk the visible Chaoxing course catalog and its page tasks."""

import ctypes
import os
import subprocess
import time
import urllib.parse
from pathlib import Path

from selenium.webdriver.common.by import By
from chaoxing import select_learning_window


CATALOG = ".posCatalog_name[onclick]"


def focus_course_edge(driver):
    """Keep the dedicated course browser visible for sites that pause background video."""
    host = urllib.parse.urlparse(driver.current_url).hostname or ""
    if os.name != "nt" or not host.endswith("chaoxing.com"):
        return False
    port_file = Path(__file__).resolve().parent / "data" / "edge-port.txt"
    try:
        port = int(port_file.read_text(encoding="ascii").strip())
        command = ("Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | "
                   f"Where-Object CommandLine -Match '--remote-debugging-port={port}' | "
                   "Select-Object -First 1 -ExpandProperty ProcessId")
        result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                                capture_output=True, text=True, timeout=8,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        edge_pid = int(result.stdout.strip())
        user32 = ctypes.windll.user32
        handles = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def inspect(hwnd, _):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == edge_pid and user32.IsWindowVisible(hwnd):
                handles.append(hwnd)
            return True
        callback = callback_type(inspect)
        user32.EnumWindows(callback, 0)
        if not handles:
            return False
        user32.ShowWindow(handles[0], 9)
        user32.keybd_event(0x12, 0, 0, 0)
        user32.keybd_event(0x12, 0, 2, 0)
        return bool(user32.SetForegroundWindow(handles[0]))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


class PendingTaskError(RuntimeError):
    """The current catalog page still needs attention; do not advance."""


def task_state(driver):
    """Return unfinished video and homework counts from the current card frame."""
    driver.switch_to.default_content()
    def has_cards(d):
        return bool(d.find_elements(By.CSS_SELECTOR, ".ans-attach-ct"))
    if not visit_frames(driver, has_cards):
        driver.switch_to.default_content()
        return None
    cards = driver.find_elements(By.CSS_SELECTOR, ".ans-attach-ct")
    videos = sum("videoContainer" in (card.get_attribute("class") or "")
                 and "ans-job-finished" not in (card.get_attribute("class") or "")
                 for card in cards)
    works = sum("videoContainer" not in (card.get_attribute("class") or "")
                and "ans-job-finished" not in (card.get_attribute("class") or "")
                and bool(card.find_elements(By.CSS_SELECTOR, "iframe"))
                for card in cards)
    driver.switch_to.default_content()
    return videos, works


def catalog_items(driver):
    driver.switch_to.default_content()
    return [(item.get_attribute("onclick"), item.get_attribute("title") or item.text.strip())
            for item in driver.find_elements(By.CSS_SELECTOR, CATALOG)
            if item.get_attribute("onclick")]


def catalog_pending(driver, onclick):
    driver.switch_to.default_content()
    item = next((x for x in driver.find_elements(By.CSS_SELECTOR, CATALOG)
                 if x.get_attribute("onclick") == onclick), None)
    if item is None:
        return False
    container = item.find_element(By.XPATH, "./ancestor::div[contains(@class,'posCatalog_select')][1]")
    counts = container.find_elements(By.CSS_SELECTOR, ".jobUnfinishCount")
    return any((x.get_attribute("value") or "0").isdigit()
               and int(x.get_attribute("value")) > 0 for x in counts)


def remaining_catalog_items(driver):
    driver.switch_to.default_content()
    return driver.execute_script("""return [...document.querySelectorAll('.posCatalog_name[onclick]')]
      .filter(x => {const c=x.closest('.posCatalog_select');
        if(!c)return false;
        const n=c.querySelector('.jobUnfinishCount');
        return (n && Number(n.value)>0) || !!c.querySelector('.catalog_points_yi');
      }).length""")


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
    focus_course_edge(driver)
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
        state = d.execute_script("return {paused:arguments[0].paused,time:arguments[0].currentTime}", video)
        if state["paused"] or state["time"] < 1:
            buttons = [b for b in d.find_elements(By.CSS_SELECTOR, ".vjs-big-play-button")
                       if b.is_displayed()]
            if buttons:
                buttons[0].click()
            else:
                d.execute_script("arguments[0].play();", video)
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
                        duration:v.duration,ready:v.readyState,
                        completed:!!window.frameElement?.closest('.ans-attach-ct')
                          ?.classList.contains('ans-job-finished')} : null;""")
        if not state:
            break
        if state["completed"]:
            driver.execute_script("document.querySelector('video')?.pause();")
            log("平台已标记视频完成，继续下一个任务。")
            driver.switch_to.default_content()
            return True
        if state["ended"] or (state["duration"] and state["time"] >= state["duration"] - 1):
            log("视频播放结束。")
            driver.switch_to.default_content()
            return True
        if state["time"] > last_time + 0.5:
            last_time = state["time"]
            last_progress = time.monotonic()
        elif time.monotonic() - last_progress > 40:
            focus_course_edge(driver)
            log("视频媒体未加载。" if state["ready"] == 0 else
                "视频播放进度持续未变化，请在浏览器检查播放限制。")
            break
        if state["paused"]:
            focus_course_edge(driver)
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
    if not select_learning_window(driver):
        raise RuntimeError("专用 Edge 中没有找到学生学习页面，请先打开课程。")
    items = catalog_items(driver)
    if not items:
        raise RuntimeError("当前页未找到超星课程目录，请先打开课程的学生学习页面。")
    log(f"目录共有 {len(items)} 个页面，开始逐页处理。")
    done = 0
    attempted = 0
    halt_reason = ""
    for index, (onclick, title) in enumerate(items, 1):
        if stopped.is_set():
            break
        driver.switch_to.default_content()
        candidates = driver.find_elements(By.CSS_SELECTOR, CATALOG)
        item = next((x for x in candidates if x.get_attribute("onclick") == onclick), None)
        if item is None:
            log(f"[{index}/{len(items)}] 目录项已变化，跳过：{title}")
            continue
        container = item.find_element(By.XPATH, "./ancestor::div[contains(@class,'posCatalog_select')][1]")
        if (container.find_elements(By.CSS_SELECTOR, ".icon_Completed")
                and not container.find_elements(By.CSS_SELECTOR, ".jobUnfinishCount, .catalog_points_yi")):
            log(f"[{index}/{len(items)}] 已完成，跳过：{title}")
            continue
        log(f"[{index}/{len(items)}] 打开：{title}")
        attempted += 1
        try:
            item.click()
            time.sleep(2)
            tabs = driver.find_elements(By.CSS_SELECTOR, "#prev_tab .prev_ul li")
            tab_count = max(1, len(tabs))
            log(f"当前节有 {tab_count} 个内页，逐页检查视频与题目。")
            for tab_index in range(tab_count):
                if stopped.is_set():
                    break
                driver.switch_to.default_content()
                tabs = driver.find_elements(By.CSS_SELECTOR, "#prev_tab .prev_ul li")
                if tabs:
                    tabs[tab_index].click()
                    time.sleep(2)
                log(f"检查内页 {tab_index + 1}/{tab_count}。")
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
                            raise PendingTaskError("视频未播放完成")
                driver.switch_to.default_content()
                # Video completion may refresh the card frame asynchronously.
                state = None
                for _ in range(30):
                    if stopped.is_set():
                        break
                    state = task_state(driver)
                    if state is not None and state[0] == 0:
                        break
                    time.sleep(1)
                if stopped.is_set():
                    break
                if state is None:
                    raise PendingTaskError("任务卡片未加载")
                if state[0]:
                    raise PendingTaskError("视频已结束，但平台尚未标记完成")
                if state[1]:
                    log(f"发现 {state[1]} 个未完成作业任务，先处理题目。")
                    if not solve_page(driver, config, stopped, log):
                        raise PendingTaskError("作业未全部填写并提交")
                    done += 1
                # A successful click is not enough to advance past a pending work card.
                for _ in range(20):
                    state = task_state(driver)
                    if state is not None and state[1] == 0:
                        break
                    time.sleep(1)
                if state is not None and state[1]:
                    raise PendingTaskError("作业提交后仍显示未完成")
            if stopped.is_set():
                break
            for _ in range(30):
                if not catalog_pending(driver, onclick) or stopped.is_set():
                    break
                time.sleep(1)
            if catalog_pending(driver, onclick):
                raise PendingTaskError("目录仍显示未完成任务点，请检查当前节")
        except PendingTaskError as exc:
            halt_reason = f"第 {index} 项 {title}：{exc}"
            log(f"[{index}/{len(items)}] 停在当前节：{title}；{exc}")
            driver.switch_to.default_content()
            break
        except Exception as exc:
            halt_reason = f"第 {index} 项 {title}：{str(exc)[:120]}"
            log(f"[{index}/{len(items)}] 停在当前节：{title}；{str(exc)[:120]}")
            driver.switch_to.default_content()
            break
    driver.switch_to.default_content()
    remaining = remaining_catalog_items(driver)
    if stopped.is_set():
        log(f"已停止：本次打开 {attempted} 项，仍有 {remaining} 项未完成。")
        return False
    if halt_reason:
        log(f"目录未完成：停在{halt_reason}；仍有 {remaining} 项未完成。")
        return False
    if remaining:
        log(f"目录未完成：本次打开 {attempted} 项，仍有 {remaining} 项未完成。")
        return False
    log(f"目录全部完成：共检查 {len(items)} 项，本次提交作业 {done} 页。")
    return True

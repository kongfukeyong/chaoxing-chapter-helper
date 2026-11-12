"""Read visible Chaoxing chapter homework from its nested frames."""

import re
import time

from selenium.webdriver.common.by import By


QUESTION_SELECTOR = ".TiMu, .questionLi"
FIELD_SELECTOR = 'input[type="radio"], input[type="checkbox"], input[type="text"], textarea'


def select_learning_window(driver):
    """Select the course tab instead of relying on Edge's initial tab."""
    original = driver.current_window_handle
    for handle in driver.window_handles:
        try:
            driver.switch_to.window(handle)
            driver.switch_to.default_content()
            if driver.find_elements(By.CSS_SELECTOR, ".posCatalog_name[onclick]"):
                return True
        except Exception:
            continue
    driver.switch_to.window(original)
    driver.switch_to.default_content()
    return False


def enter_homework_tab(driver, stopped):
    """Find questions on any inner page of the selected course section."""
    driver.switch_to.default_content()
    if enter_homework_frame(driver):
        return True
    driver.switch_to.default_content()
    count = len(driver.find_elements(By.CSS_SELECTOR, "#prev_tab .prev_ul li"))
    for index in range(count):
        if stopped.is_set():
            return False
        driver.switch_to.default_content()
        tabs = driver.find_elements(By.CSS_SELECTOR, "#prev_tab .prev_ul li")
        tabs[index].click()
        for _ in range(10):
            if stopped.is_set():
                return False
            driver.switch_to.default_content()
            if enter_homework_frame(driver):
                return True
            time.sleep(0.5)
    driver.switch_to.default_content()
    return False


def enter_homework_frame(driver, depth=0):
    """Leave Selenium in the frame containing visible homework questions."""
    if driver.find_elements(By.CSS_SELECTOR, QUESTION_SELECTOR):
        return True
    if depth >= 5:
        return False
    frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
    for frame in frames:
        try:
            driver.switch_to.frame(frame)
            if enter_homework_frame(driver, depth + 1):
                return True
        except Exception:
            pass
        driver.switch_to.parent_frame()
    return False


def read_homework(driver, Question, log, stopped):
    select_learning_window(driver)
    if not enter_homework_tab(driver, stopped):
        return []
    groups = []
    for block in driver.find_elements(By.CSS_SELECTOR, QUESTION_SELECTOR):
        if stopped.is_set():
            break
        # Nested question wrappers are common. Process only the innermost node.
        if block.find_elements(By.CSS_SELECTOR, QUESTION_SELECTOR):
            continue
        fields = [x for x in block.find_elements(By.CSS_SELECTOR, FIELD_SELECTOR)
                  if x.is_displayed() and x.is_enabled()]
        if not fields:
            visual_choices = block.find_elements(By.CSS_SELECTOR, ".Zy_ulTop li[onclick]")
            if not visual_choices:
                continue
        else:
            visual_choices = []
        titles = block.find_elements(By.CSS_SELECTOR, ".Zy_TItle, .Zy_TItle_p, .questionTitle, .stem")
        title = (titles[0].text if titles else block.text).strip()
        title = re.sub(r"\s+", " ", title)[:4000]
        if not title:
            continue
        questions = []
        if visual_choices:
            qtype = visual_choices[0].get_attribute("qtype")
            options = []
            for index, item in enumerate(visual_choices):
                letter = chr(65 + index)
                parts = item.find_elements(By.CSS_SELECTOR, "a")
                label = (parts[0].text if parts else item.text).strip()
                options.append((letter, label or letter, item))
            kind = "multiple" if qtype == "1" else "single"
            questions.append(Question(1, kind, title, options=options,
                                      choice_style="chaoxing"))
        by_name = {}
        for field in fields:
            kind = (field.get_attribute("type") or "").lower()
            if kind in ("radio", "checkbox"):
                by_name.setdefault(field.get_attribute("name") or "_one", []).append(field)
        for choices in by_name.values():
            if len(choices) < 2:
                continue
            options = []
            for index, field in enumerate(choices):
                letter = chr(65 + index)
                parents = field.find_elements(By.XPATH, "./ancestor::li[1] | ./ancestor::label[1]")
                parent = parents[0] if parents else field.find_element(By.XPATH, "./parent::*")
                label = parent.text.strip()
                options.append((letter, label or letter, field))
            kind = "multiple" if choices[0].get_attribute("type") == "checkbox" else "single"
            questions.append(Question(len(questions) + 1, kind, title, options=options))
        text_fields = [field for field in fields if (field.get_attribute("type") or "").lower()
                       not in ("radio", "checkbox")]
        for index, field in enumerate(text_fields, 1):
            questions.append(Question(len(questions) + 1, "text", title,
                                      element=field, blank_label=f"第 {index} 空"))
        if questions:
            groups.append(("", questions))
    if not groups:
        log("已进入超星作业框架，但没有找到可填写的题目；请确认作业已加载且处于答题状态。")
    return groups


def confirm_submit_dialog(driver, depth=0):
    """Click the visible Chaoxing confirmation, wherever its frame lives."""
    for dialog in driver.find_elements(By.CSS_SELECTOR,
        "#workpop, .layui-layer, .popDiv, [role='dialog']"):
        if not dialog.is_displayed() or "提交" not in dialog.text:
            continue
        for control in dialog.find_elements(By.CSS_SELECTOR,
            "a, button, input[type='button']"):
            label = (control.text or control.get_attribute("value") or "").strip()
            if label in ("提交", "确认提交", "确定", "确认") and control.is_displayed():
                control.click()
                return True
    if depth >= 5:
        return False
    for frame in driver.find_elements(By.CSS_SELECTOR, "iframe, frame"):
        try:
            driver.switch_to.frame(frame)
            if confirm_submit_dialog(driver, depth + 1):
                return True
        except Exception:
            pass
        driver.switch_to.parent_frame()
    return False


def work_card_complete(driver, depth=0):
    cards = [card for card in driver.find_elements(By.CSS_SELECTOR, ".ans-attach-ct")
             if "videoContainer" not in (card.get_attribute("class") or "")
             and card.find_elements(By.CSS_SELECTOR, "iframe")]
    if cards:
        return all("ans-job-finished" in (card.get_attribute("class") or "")
                   for card in cards)
    if depth >= 5:
        return None
    for frame in driver.find_elements(By.CSS_SELECTOR, "iframe, frame"):
        try:
            driver.switch_to.frame(frame)
            result = work_card_complete(driver, depth + 1)
            if result is not None:
                return result
        except Exception:
            pass
        driver.switch_to.parent_frame()
    return None


def wait_for_completion(driver, stopped, log):
    for _ in range(30):
        if stopped.is_set():
            return False
        driver.switch_to.default_content()
        result = work_card_complete(driver)
        if result is True:
            driver.switch_to.default_content()
            log("平台已标记作业完成。")
            return True
        if result is None:
            driver.switch_to.default_content()
            return True  # Source-only fixtures may not have the course card.
        time.sleep(1)
    driver.switch_to.default_content()
    log("提交已确认，但平台仍显示作业未完成。")
    return False


def submit_homework(driver, log, stopped):
    """Submit a fully answered homework and handle its cross-frame confirmation."""
    driver.switch_to.default_content()
    if confirm_submit_dialog(driver):
        driver.switch_to.default_content()
        log("已确认现有的作业提交弹窗。")
        return wait_for_completion(driver, stopped, log)
    driver.switch_to.default_content()
    if not enter_homework_frame(driver):
        log("自动提交失败：作业题目框架已消失。")
        return False
    buttons = [x for x in driver.find_elements(By.CSS_SELECTOR, ".ZY_sub a.btnSubmit")
               if x.is_displayed() and x.is_enabled()]
    if len(buttons) != 1:
        log("自动提交失败：未找到唯一的作业提交按钮。")
        driver.switch_to.default_content()
        return False
    buttons[0].click()
    for _ in range(60):
        if stopped.is_set():
            driver.switch_to.default_content()
            return False
        try:
            driver.switch_to.alert.accept()
            driver.switch_to.default_content()
            log("已确认浏览器提交提示。")
            return wait_for_completion(driver, stopped, log)
        except Exception:
            pass
        driver.switch_to.default_content()
        if confirm_submit_dialog(driver):
            driver.switch_to.default_content()
            log("已确认作业提交弹窗。")
            return wait_for_completion(driver, stopped, log)
        time.sleep(0.5)
    driver.switch_to.default_content()
    log("提交按钮已点击，但未找到确认结果；当前页不标记完成。")
    return False

"""Read visible Chaoxing chapter homework from its nested frames."""

import re

from selenium.webdriver.common.by import By


QUESTION_SELECTOR = ".TiMu, .questionLi"
FIELD_SELECTOR = 'input[type="radio"], input[type="checkbox"], input[type="text"], textarea'


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
    driver.switch_to.default_content()
    if not enter_homework_frame(driver):
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
            continue
        titles = block.find_elements(By.CSS_SELECTOR, ".Zy_TItle, .Zy_TItle_p, .questionTitle, .stem")
        title = (titles[0].text if titles else block.text).strip()
        title = re.sub(r"\s+", " ", title)[:4000]
        if not title:
            continue
        questions = []
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

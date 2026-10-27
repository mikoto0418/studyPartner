"""Browser regression with intercepted APIs; does not read or modify a real database.

Start `npm run dev -- --host 127.0.0.1 --port 5178`, then run this with Python/Playwright.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('EDITOR_TEST_URL', 'http://127.0.0.1:5178')


async def main():
    now = datetime.now(timezone.utc)
    due = (now + timedelta(minutes=30)).isoformat()
    attempt = {'id': 'attempt-editor-test', 'status': 'in_progress', 'started_at': now.isoformat(), 'answer_deadline': due}
    paper = {'id': 'editor-test', 'title': '编程工作台验收', 'due_at': due, 'require_fullscreen': True,
             'fullscreen_exit_auto_submit': False, 'attempt_status': 'in_progress', 'question_count': 2, 'total_score': 40}
    questions = [{'id': f'q{i}', 'question_type': 'code', 'language': 'multi', 'score': 20,
                  'stem': f'第 {i} 题：按要求输出结果。\n输入格式：从标准输入读取。\n输出格式：输出计算结果。', 'starter_code': ''}
                 for i in (1, 2)]
    saved, events, submitted = {}, [], []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel='chrome', headless=True)
        context = await browser.new_context(viewport={'width': 1366, 'height': 768}, permissions=['clipboard-read', 'clipboard-write'])
        await context.add_init_script("localStorage.setItem('sp_token','mock');localStorage.setItem('sp_role','student');localStorage.setItem('sp_username','editor-test')")
        page = await context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        async def api(route):
            request, path = route.request, route.request.url.split('/api/v1')[-1]
            data = None
            if path == '/auth/me':
                data = {'id': 'student', 'username': 'editor-test', 'display_name': '编辑器验收', 'requires_identity_confirmation': False}
            elif path == '/assessment/student/clock':
                data = {'server_time': datetime.now(timezone.utc).isoformat()}
            elif path == '/assessment/student/papers':
                data = [paper]
            elif path.endswith('/questions'):
                data = questions
            elif path.endswith('/attempts'):
                data = attempt
            elif path.endswith('/answers') and request.method == 'GET':
                data = {'attempt_id': attempt['id'], 'answers': list(saved.values())}
            elif path.endswith('/answers'):
                for answer in request.post_data_json['answers']:
                    saved[answer['question_id']] = answer
            elif path.endswith('/run'):
                data = {'status': 'ok', 'runs_left': 19, 'cases': [{'index': 0, 'status': 'ok', 'actual_output': '1\n', 'time_ms': 3}]}
            elif path.endswith('/submit'):
                submitted.append(request.post_data_json)
                await asyncio.sleep(1)
                attempt.update(status='submitted', score=40, duration_seconds=20)
                paper['attempt_status'] = 'submitted'
                data = attempt
            elif path.endswith('/behavior/batch'):
                events.extend(request.post_data_json['events'])
            else:
                data = []
            await route.fulfill(json={'code': 0, 'data': data})

        await page.route('**/api/v1/**', api)
        await page.goto(BASE + '/student/assessment/editor-test')
        await page.get_by_role('button', name='继续答题', exact=True).click()
        editor = page.get_by_role('textbox', name='代码编辑器', exact=True)
        await expect(editor).to_be_visible()
        await expect(page.get_by_text('退出系统', exact=True)).to_have_count(0)
        left = await page.get_by_role('region', name='题目说明', exact=True).bounding_box()
        right = await page.get_by_role('region', name='代码与自测', exact=True).bounding_box()
        assert left['x'] + left['width'] <= right['x'] and abs(left['y'] - right['y']) < 2
        divider = page.get_by_role('separator')
        await divider.focus()
        await divider.press('ArrowRight')
        assert await divider.get_attribute('aria-valuenow') == '45'

        async def code():
            return '\n'.join(await editor.locator('.cm-line').all_text_contents())

        async def reset():
            await editor.click()
            await editor.press('Control+a')
            await editor.press('Backspace')

        await editor.click()
        await editor.press_sequentially("if value == '#':")
        await editor.press('Enter')
        assert (await code()).startswith("if value == '#':\n    "), repr(await code())
        await reset()
        await editor.press('Tab')
        assert await code() == '    '
        await editor.press('Shift+Tab')
        assert await code() == ''
        await editor.press('(')
        assert await code() == '()'
        await editor.press('Backspace')
        assert await code() == ''
        await editor.press_sequentially('print(1)')
        await editor.press('Control+s')
        await expect(page.get_by_text('已保存到服务器', exact=False)).to_be_visible()
        assert saved['q1']['answer']['code'] == 'print(1)'
        await editor.press('Control+f')
        await expect(page.locator('.cm-search')).to_be_visible()
        await page.locator('.cm-search input').first.press('Escape')

        # A different question must not replace the original question's undo history.
        await page.get_by_role('button', name='下一题', exact=True).click()
        await editor.click()
        await editor.press_sequentially('second')
        await page.get_by_role('button', name='上一题', exact=True).click()
        assert await code() == 'print(1)'
        await editor.click()
        await editor.press('Control+z')
        assert await code() != 'print(1)'
        await editor.press('Control+y')
        assert await code() == 'print(1)'

        # Normal copy/cut/paste inside the exam stays editable; external insertion is blocked.
        await editor.press('Control+a')
        await editor.press('Control+c')
        await editor.press('End')
        await editor.press('Enter')
        await editor.press('Control+v')
        assert await code() == 'print(1)\nprint(1)', repr(await code())
        await page.evaluate("navigator.clipboard.writeText('external code')")
        previous = await code()
        await editor.press('Control+v')
        assert await code() == previous
        stdin = page.get_by_role('textbox', name='标准输入', exact=True)
        await stdin.click()
        await stdin.press('Control+v')
        await expect(stdin).to_have_value('external code')

        for language in ('python', 'java', 'c', 'cpp'):
            await page.get_by_label('编程语言').select_option(language)
            await reset()
            await editor.press_sequentially('int main') if language != 'python' else await editor.press_sequentially('print')
            await editor.press('(')
            assert (await code()).endswith('()')
        await reset()
        await editor.press_sequentially('print(1)')
        await page.get_by_role('button', name='运行自测', exact=True).click()
        await expect(page.get_by_text('标准输出', exact=True)).to_be_visible()
        await editor.click()
        await editor.press('End')
        await editor.press_sequentially('x')
        await expect(page.get_by_text('代码或语言已修改，以下为上一次运行的结果。')).to_be_visible()
        if os.environ.get('WORKSPACE_SCREENSHOT'):
            target = Path(os.environ['WORKSPACE_SCREENSHOT'])
            target.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(target))

        # Responsive layout keeps the editor inside the viewport.
        await page.set_viewport_size({'width': 720, 'height': 850})
        await page.get_by_role('button', name='代码与自测', exact=True).click()
        await expect(editor).to_be_visible()
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        await page.set_viewport_size({'width': 1366, 'height': 768})
        await page.wait_for_timeout(5200)
        edits = [e for e in events if e['event_type'] == 'answer_edit']
        assert edits and all(e['payload']['question_id'] in ('q1', 'q2') for e in edits)
        assert all(len(e['payload'].get('inserted_text', '')) <= 4000 for e in edits)
        blocked = [e for e in events if e['event_type'].startswith('blocked_')]
        assert len(blocked) == 1 and blocked[0]['event_type'] == 'blocked_paste', blocked

        # Browser modal must trap interaction; navigation checks survive a cleared local hint.
        await page.evaluate('document.exitFullscreen()')
        dialog = page.locator('dialog.exam-resume')
        await expect(dialog).to_be_visible()
        await page.keyboard.press('Escape')
        await expect(dialog).to_be_visible()
        await page.keyboard.press('Tab')
        assert await page.evaluate("document.activeElement.textContent.trim() === '继续答题'")
        await page.evaluate("localStorage.removeItem('sp_exam_lock:editor-test')")
        await page.goto(BASE + '/student/dashboard')
        await page.wait_for_url('**/student/assessment/editor-test')
        await page.get_by_role('button', name='继续答题', exact=True).click()
        await expect(editor).to_be_visible()
        await page.reload()
        await expect(dialog).to_be_visible()
        await page.get_by_role('button', name='继续答题', exact=True).click()
        await expect(editor).to_be_visible()

        await page.get_by_role('button', name='提交整场考试', exact=True).click()
        await page.get_by_role('button', name='确认交卷', exact=True).click()
        await expect(editor).to_have_attribute('contenteditable', 'false')
        await expect(page.get_by_label('编程语言')).to_be_disabled()
        await expect(page.get_by_text('本次作答已提交', exact=True)).to_be_visible()
        await page.goto(BASE + '/student/dashboard')
        await page.wait_for_url('**/student/dashboard')
        await expect(page.locator('dialog.exam-resume[open]')).to_have_count(0)
        assert submitted and not errors, errors
        print('PASS: split/responsive layout; 4 languages; indentation/pairs/history/find/save; per-question history; internal/external clipboard; stale run result; semantic edits; submitting read-only')
        await browser.close()


asyncio.run(main())

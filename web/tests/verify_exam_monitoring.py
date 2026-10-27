"""Teacher browser regression using mock APIs; never touches an exam database."""
import asyncio
import os
from datetime import datetime, timezone
from playwright.async_api import async_playwright, expect

BASE = os.environ.get('EDITOR_TEST_URL', 'http://127.0.0.1:5179')

async def main():
    stamp = datetime.now(timezone.utc).isoformat()
    attempt = dict(id='attempt', student_id='student', student_name='测试考生', username='teststudent',
        status='in_progress', score=None, started_at=stamp, event_count=2, flagged_count=0,
        left_count=0, fullscreen_exit_count=0, suspicious=False, pending_grade_count=0)
    paper = dict(id='paper', title='监考回归', question_count=2, total_score=100)
    answers = [dict(question_id=f'q{i}', order_index=i-1, question_type='code', stem=f'题目 {i}',
        answer={'language':'cpp', 'code':'int main() { return 0; }'} if i == 1 else None,
        has_saved_answer=i==1, saved_at=stamp if i==1 else None, language='cpp' if i==1 else 'multi',
        attempt_status='in_progress', max_score=50, score=0, graded=False) for i in (1,2)]
    polls, fail_answers = [], False
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel='chrome', headless=True)
        page = await browser.new_page(viewport={'width':1440, 'height':1000})
        await page.add_init_script("localStorage.setItem('sp_token','mock');localStorage.setItem('sp_role','teacher');localStorage.setItem('sp_username','teacher')")
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        async def api(route):
            path = route.request.url.split('/api/v1')[-1]
            data = []
            if path == '/auth/me':
                data = {'id':'teacher','username':'teacher','requires_identity_confirmation':False}
            elif path == '/assessment/papers': data = [paper]
            elif path.endswith('/attempts'):
                polls.append(1); data = [attempt]
            elif path.endswith('/questions'): data = answers
            elif path.endswith('/answers'):
                if fail_answers:
                    await route.fulfill(status=503, json={'code':50000, 'message':'模拟连接异常'})
                    return
                data = answers
            await route.fulfill(json={'code':0,'data':data})
        await page.route('**/api/v1/**', api)
        await page.goto(BASE + '/teacher/assessment-monitor')
        await page.get_by_role('button',name='查看代码',exact=True).click()
        drawer = page.get_by_role('dialog')
        await expect(drawer.get_by_text('服务器已保存草稿 · 尚未交卷',exact=True)).to_be_visible()
        await expect(page.get_by_label('学生代码，只读')).to_have_text('int main() { return 0; }')
        await expect(drawer.get_by_text('C++17',exact=True)).to_be_visible()
        await drawer.get_by_role('button',name='第 2 题',exact=False).click()
        await expect(drawer.get_by_text('这道题尚未保存到服务器',exact=True)).to_be_visible()
        await drawer.get_by_role('button',name='第 1 题',exact=False).click()
        # Polling changes list status, while the open code snapshot remains stable.
        attempt.update(status='submitted',score=100)
        answers[0].update(attempt_status='submitted',answer={'language':'cpp','code':'int main() { return 1; }'},graded=True,score=50)
        await page.wait_for_timeout(5500)
        assert len(polls) >= 2
        await expect(page.get_by_label('学生代码，只读')).to_have_text('int main() { return 0; }')
        await expect(drawer.get_by_text('服务器已保存草稿 · 尚未交卷',exact=True)).to_be_visible()
        await drawer.get_by_role('button',name='刷新答案',exact=True).click()
        await expect(drawer.get_by_text('已交卷答案',exact=True)).to_be_visible()
        await expect(page.get_by_label('学生代码，只读')).to_have_text('int main() { return 1; }')
        fail_answers = True
        await drawer.get_by_role('button',name='刷新答案',exact=True).click()
        await expect(drawer.get_by_role('alert')).to_be_visible()
        await expect(page.get_by_label('学生代码，只读')).to_have_text('int main() { return 1; }')
        assert not errors, errors
        await browser.close()
    print('PASS: in-progress code access, all questions, actual language, polling, snapshot stability, final refresh, request failure retains code')

asyncio.run(main())

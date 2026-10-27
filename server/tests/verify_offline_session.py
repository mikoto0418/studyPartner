"""Exercise live Nginx, API, Redis, worker and judge on the isolated offline test stack."""
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
BASE = 'http://127.0.0.1:18080'
DATA = json.loads((ROOT / 'server/app/data/exam_1022.json').read_text(encoding='utf-8'))
client = httpx.Client(base_url=BASE + '/api/v1', timeout=180)
def call(method, path, headers=None, data=None):
    response = client.request(method, path, headers=headers, json=data)
    assert response.status_code == 200, (path, response.status_code, response.text[:500])
    return response.json()['data']
def login(username):
    return {'Authorization': 'Bearer ' + call('POST', '/auth/login', data={'username': username, 'password': username})['access_token']}
def paper(teacher, title, due, start=None, force=False):
    p = call('POST', '/assessment/papers', teacher, {'title': title})
    call('PUT', f"/assessment/papers/{p['id']}/questions", teacher, {'questions': DATA['questions']})
    from uuid import NAMESPACE_URL, uuid5
    cid = str(uuid5(NAMESPACE_URL, 'studypartner:interview:1022:class'))
    call('POST', f"/assessment/papers/{p['id']}/publish", teacher, {
        'publish_target': {'type': 'class', 'ids': [cid]},
        'publish_at': start.isoformat() if start else None, 'due_at': due.isoformat(),
        'require_fullscreen': True, 'fullscreen_exit_auto_submit': force,
    })
    return p
def browser_login(page, username):
    page.goto(BASE + '/login')
    page.get_by_placeholder('用户名或邮箱').fill(username)
    page.get_by_placeholder('请输入密码', exact=True).fill(username)
    page.get_by_role('button', name='进入协同空间').click()
    page.wait_for_url('**/student/dashboard')

def main():
    teacher = login('tea10221')
    now = datetime.now(timezone.utc)
    scheduled = paper(teacher, '离线短时限验收', now + timedelta(seconds=120), now + timedelta(seconds=8))
    pid = scheduled['id']
    students = []
    for i in range(1, 5):
        h = login(f'stu1022{i:02d}')
        call('POST', '/auth/identity', h, {'name': f'离线验收{i}'})
        students.append(h)
    early = client.get(f'/assessment/student/papers/{pid}/questions', headers=students[0])
    assert early.status_code == 404, early.text
    while datetime.now(timezone.utc) < now + timedelta(seconds=9): time.sleep(.25)
    questions = call('GET', f'/assessment/student/papers/{pid}/questions', students[0])
    assert len(questions) == 5
    attempts = []
    for i, (lang, suffix) in enumerate((('python','py'),('java','java'),('c','c'),('cpp','cpp'))):
        attempt = call('POST', f'/assessment/student/papers/{pid}/attempts', students[i])
        attempts.append(attempt)
        template = (ROOT / f'server/tests/fixtures/exam_1022/reference.{suffix}.tmpl').read_text(encoding='utf-8')
        answers = [{'question_id': q['id'], 'answer': {'language': lang, 'code': template.replace('__TASK__', str(t))}} for t, q in enumerate(questions, 1)]
        call('PUT', f"/assessment/student/attempts/{attempt['id']}/answers", students[i], {'answers': answers})
        run = call('POST', f"/assessment/student/attempts/{attempt['id']}/questions/{questions[1]['id']}/run", students[i], {'language':lang, 'code':answers[1]['answer']['code'], 'stdin':DATA['questions'][1]['test_cases'][0]['input']})
        assert run['status'] == 'ok' and run['cases'][0]['actual_output'].strip() == DATA['questions'][1]['test_cases'][0]['expected_output'].strip(), run
        if i >= 2:
            result = call('POST', f"/assessment/student/attempts/{attempt['id']}/submit", students[i], {'answers':answers})
            assert result['status'] == 'submitted' and result['score'] == 140
    print('PASS offline four-language self-runs; C/C++ manual submissions 140; Python/Java saved for timed collection', flush=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context()
        errors, external = [], []
        def route(req):
            if not req.request.url.startswith(BASE):
                external.append(req.request.url)
                req.abort()
            else: req.continue_()
        context.route('**/*', route)
        # Student computer clock deliberately wrong by seven days.
        context.add_init_script('Date.now = () => 1793210000000')
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        browser_login(page, 'stu102201')
        page.goto(BASE + '/student/assessment/' + pid)
        page.get_by_role('button', name='进入全屏并开始作答', exact=True).click()
        assert page.evaluate('!!document.fullscreenElement')
        expect(page.get_by_label('编程语言')).to_have_value('python')
        expect(page.get_by_placeholder('在这里写你的代码（禁止粘贴）')).to_have_value((ROOT/'server/tests/fixtures/exam_1022/reference.py.tmpl').read_text(encoding='utf-8').replace('__TASK__','1'))
        for _ in range(3):
            page.evaluate('document.exitFullscreen()')
            expect(page.get_by_text('已退出全屏模式', exact=True)).to_be_visible()
            page.get_by_role('button', name='恢复全屏', exact=False).click()
            assert page.evaluate('!!document.fullscreenElement')
        assert call('GET', f'/assessment/student/papers/{pid}/answers', students[0])['status'] == 'in_progress'
        # Simulate interrupted Wi-Fi, save locally, then reconnect before deadline.
        context.set_offline(True)
        editor = page.get_by_placeholder('在这里写你的代码（禁止粘贴）')
        updated = editor.input_value() + '\n# offline edit\n'
        editor.fill(updated)
        expect(page.get_by_text('保存失败，正在重试；请勿关闭页面', exact=False)).to_be_visible(timeout=15000)
        context.set_offline(False)
        expect(page.get_by_text('已保存到服务器', exact=False)).to_be_visible(timeout=15000)
        page.reload()
        page.get_by_role('button', name='进入全屏并开始作答', exact=True).click()
        expect(editor).to_have_value(updated)
        print('PASS real fullscreen; 3 exits do not submit; wrong client clock; disconnect/reconnect and refresh preserve code', flush=True)
        # Frontend timer submits Python; Java has no browser and must be collected by beat/worker.
        expect(page.get_by_text('140', exact=True).first).to_be_visible(timeout=150000)
        assert not errors, errors
        assert not external, external
        context.close()
        browser.close()
    end_wait = time.monotonic()+60
    while time.monotonic()<end_wait:
        rows = call('GET', f'/assessment/papers/{pid}/attempts', teacher)
        if len(rows)==4 and all(r['status']=='submitted' and r['score']==140 for r in rows): break
        time.sleep(1)
    else: raise AssertionError(rows)
    late = client.put(f"/assessment/student/attempts/{attempts[1]['id']}/answers", headers=students[1], json={'answers':[]})
    assert late.status_code == 400, late.text
    print('PASS timed frontend + closed-browser background collection: all four scores persisted as 140; late writes rejected; no external page requests', flush=True)

if __name__ == '__main__': main()

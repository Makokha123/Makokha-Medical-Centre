import requests

essentials = [
    '/api/conversations',
    '/api/get_or_create_conversation?user_id=1',
    '/api/conversation_messages?user_id=1&page=1&per_page=25',
    '/api/get_users?q=test',
]
base = 'http://127.0.0.1:5000'
for p in essentials:
    url = base + p
    print('\n===', url, '===')
    try:
        r = requests.get(url, timeout=10, allow_redirects=False)
        print('Status:', r.status_code)
        print('Headers:', {k: v for k, v in r.headers.items() if k.lower() in ('content-type','location')})
        text = r.text
        if len(text) > 800:
            print(text[:800] + '...')
        else:
            print(text)
    except Exception as e:
        print('Request failed:', type(e), e)

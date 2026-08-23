import os
import re

frontend_dir = r'e:\unihack\product-intelligence\frontend\src\components'

for file in os.listdir(frontend_dir):
    if file.endswith('.jsx'):
        path = os.path.join(frontend_dir, file)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace empty API URLs with localtunnel URL
        content = re.sub(r'const API\s*=\s*[\'\"].*?[\'\"]', "const API = 'https://unilog-backend-api.loca.lt'", content)
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

# Also update App.jsx
app_path = r'e:\unihack\product-intelligence\frontend\src\App.jsx'
with open(app_path, 'r', encoding='utf-8') as f:
    app_content = f.read()

app_content = re.sub(r'fetch\([\'\"]/jobs', "fetch('https://unilog-backend-api.loca.lt/jobs", app_content)
app_content = re.sub(r'fetch\([\'\"]/metrics', "fetch('https://unilog-backend-api.loca.lt/metrics", app_content)

with open(app_path, 'w', encoding='utf-8') as f:
    f.write(app_content)

print('API URLs updated to localtunnel!')

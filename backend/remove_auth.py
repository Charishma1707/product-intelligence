import os
import re

# 1. Update Backend (main.py)
backend_file = r'e:\unihack\product-intelligence\backend\main.py'
with open(backend_file, 'r', encoding='utf-8') as f:
    backend_code = f.read()

# Remove authentication dependency from endpoints
backend_code = re.sub(r',\s*user:\s*str\s*=\s*Depends\(authenticate\)', '', backend_code)
backend_code = re.sub(r'user:\s*str\s*=\s*Depends\(authenticate\)', '', backend_code)
# Remove the authenticate function block and security dependency if needed, but the regex above removes it from routes.
# Let's just remove the authenticate function entirely.
backend_code = re.sub(r'security = HTTPBasic\(\)\n\ndef authenticate.*?\n    return credentials\.username\n', '', backend_code, flags=re.DOTALL)

with open(backend_file, 'w', encoding='utf-8') as f:
    f.write(backend_code)
print("Removed Auth from Backend main.py")

# 2. Update Frontend (React components)
frontend_dir = r'e:\unihack\product-intelligence\frontend\src'
for root, _, files in os.walk(frontend_dir):
    for file in files:
        if file.endswith('.jsx') or file.endswith('.js'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            
            original_code = code
            
            # Remove Authorization header dictionaries in fetch calls
            code = code.replace(", { headers: { 'Authorization': 'Basic YWRtaW46dW5paGFjaw==' } }", "")
            code = code.replace(", { headers: { Authorization: AUTH } }", "")
            
            # Remove Authorization key-value pairs in larger header objects
            code = re.sub(r'[\'"]?Authorization[\'"]?\s*:\s*[\'"]Basic YWRtaW46dW5paGFjaw==[\'"],?\s*', '', code)
            
            # Remove AUTH constant in ReviewQueue.jsx if it exists
            code = code.replace("const AUTH = 'Basic YWRtaW46dW5paGFjaw=='\n", "")

            if code != original_code:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(code)
                print(f"Removed Auth from {file}")

print("Auth removal complete!")

import re

main_file = r'e:\unihack\product-intelligence\backend\main.py'
with open(main_file, 'r', encoding='utf-8') as f:
    code = f.read()

# Add a reset endpoint if it doesn't exist
if '@app.post("/reset")' not in code:
    reset_endpoint = """
import subprocess

@app.post("/reset")
async def reset_pipeline():
    try:
        # Allow passing the correct python executable
        subprocess.run(['python', 'reset_pipeline.py'], check=True, cwd=str(Path(__file__).parent))
        return {"status": "success", "message": "Pipeline completely reset!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
"""
    # Insert before the first route
    code = code.replace("app = FastAPI(", "app = FastAPI(" + reset_endpoint)
    
    with open(main_file, 'w', encoding='utf-8') as f:
        f.write(code)
    print("Reset endpoint added.")
else:
    print("Reset endpoint already exists.")

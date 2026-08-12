import os
import json
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

# 1. Khai báo mỏ neo đường dẫn tuyệt đối
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
WIKI_OUTPUT_DIR = BACKEND_DIR / "wiki"

# Đảm bảo thư mục wiki và thư mục con symbols tồn tại trước khi ghi file
WIKI_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(WIKI_OUTPUT_DIR / "symbols").mkdir(parents=True, exist_ok=True)

def get_template_env():
    # Đồng bộ dùng Pathlib cho nhất quán
    current_dir = Path(__file__).resolve().parent
    template_dir = current_dir / 'templates'
    return Environment(loader=FileSystemLoader(str(template_dir)))

def render_html_page(template_name: str, section_data: dict):
    """
    Hàm render tổng quát.
    Nhận tên file template (ví dụ: 'tech.html') và dữ liệu section (từ Member 3).
    """
    env = get_template_env()
    
    # Load đúng template dựa vào tên file
    template = env.get_template(template_name)
    
    # Truyền dữ liệu vào Jinja2
    html_output = template.render(section=section_data)
    
    # 2. Trực tiếp lưu file bằng hằng số WIKI_OUTPUT_DIR
    output_path = WIKI_OUTPUT_DIR / template_name
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_output)

def render_symbol_pages(repository_index: dict):
    """
    Hàm render symbols nhận thẳng dữ liệu index từ tham số.
    """
    symbols = repository_index.get('symbols', [])
    if not symbols:
        return
        
    env = get_template_env()
    template = env.get_template('symbol.html')
    
    count = 0
    for symbol in symbols:
        fqn = symbol.get('fully_qualified_name')
        if not fqn:
            continue
            
        safe_filename = fqn.replace('<', '_').replace('>', '_') + '.html'
        html_output = template.render(symbol=symbol)
        
        # 3. Sử dụng hằng số cho đường dẫn thư mục symbols
        output_path = WIKI_OUTPUT_DIR / "symbols" / safe_filename
        with open(output_path, 'w', encoding='utf-8') as out_f:
            out_f.write(html_output)
        count += 1

def generate_search_index(repository_index):
    """Tạo file JSON chứa index tìm kiếm cho toàn bộ website"""
    search_data = [
        {"name": "Technology Stack", "url": "tech.html"},
        {"name": "Architecture", "url": "architecture.html"},
        {"name": "Modules", "url": "modules.html"},
        {"name": "Tests", "url": "tests.html"}
    ]
    
    # Lấy danh sách symbols
    for symbol in repository_index.get('symbols', []):
        fqn = symbol.get('fully_qualified_name')
        if fqn:
            safe_filename = fqn.replace('<', '_').replace('>', '_') + '.html'
            search_data.append({"name": fqn, "url": f"symbols/{safe_filename}"})
            
    # 4. Sử dụng hằng số cho đường dẫn file index
    index_path = WIKI_OUTPUT_DIR / "search_index.json"
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(search_data, f, ensure_ascii=False)
    print("✅ Đã tạo Search Index (search_index.json)")
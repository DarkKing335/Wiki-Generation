import os
import json
from jinja2 import Environment, FileSystemLoader

def get_template_env():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_dir = os.path.join(current_dir, 'templates')
    return Environment(loader=FileSystemLoader(template_dir))

def save_html(filename, html_content):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
    wiki_dir = os.path.join(repo_root, 'wiki')
    os.makedirs(wiki_dir, exist_ok=True)
    
    output_path = os.path.join(wiki_dir, filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

def render_html_page(template_name: str, section_data: dict):
    """
    Hàm render tổng quát.
    Nhận tên file template (ví dụ: 'tech.html') và dữ liệu section (từ Member 3).
    """
    env = get_template_env()
    
    # Load đúng template dựa vào tên file (tech.html, architecture.html,...)
    template = env.get_template(template_name)
    
    # Truyền dữ liệu vào Jinja2
    html_output = template.render(section=section_data)
    
    # Lưu file
    save_html(template_name, html_output)

def render_symbol_pages(repository_index: dict):
    """
    Hàm render symbols nhận thẳng dữ liệu index từ tham số 
    chứ không tự đọc file JSON cứng nữa.
    """
    symbols = repository_index.get('symbols', [])
    if not symbols:
        return
        
    env = get_template_env()
    template = env.get_template('symbol.html')
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
    symbols_dir = os.path.join(repo_root, 'wiki', 'symbols')
    os.makedirs(symbols_dir, exist_ok=True)
    
    count = 0
    for symbol in symbols:
        fqn = symbol.get('fully_qualified_name')
        if not fqn:
            continue
            
        safe_filename = fqn.replace('<', '_').replace('>', '_') + '.html'
        html_output = template.render(symbol=symbol)
        
        output_path = os.path.join(symbols_dir, safe_filename)
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
            # Dùng đường dẫn tương đối cho thư mục symbols
            search_data.append({"name": fqn, "url": f"symbols/{safe_filename}"})
            
    # Lưu ra file search_index.json
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))
    index_path = os.path.join(repo_root, 'wiki', 'search_index.json')
    
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(search_data, f, ensure_ascii=False)
    print("✅ Đã tạo Search Index (search_index.json)")
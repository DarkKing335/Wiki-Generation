import argparse
import sys
import os
from pathlib import Path

# Giả định các module của các thành viên khác đã sẵn sàng
# from core_indexing.indexer import build_repository_index
# from ai_analysis.taxonomy.heuristic import build_taxonomy_tree
# from ai_analysis.content import ContentGenerator
# from ai_analysis.llm.ollama import OllamaClient
# from ai_analysis.llm.null import NullLLMClient

# Import module render HTML của bạn (Member 4)
from wiki_generation.renderer import (
    render_html_page,
    render_symbol_pages
)

def run_analysis_pipeline(target_path: str, use_llm: bool):
    """Thực thi toàn bộ luồng phân tích end-to-end."""
    target_dir = Path(target_path).resolve()
    if not target_dir.exists():
        print(f"❌ Lỗi: Không tìm thấy đường dẫn '{target_dir}'")
        sys.exit(1)

    print(f"🚀 Bắt đầu phân tích dự án tại: {target_dir}")
    print(f"🤖 Chế độ AI (LLM): {'BẬT' if use_llm else 'TẮT'}")
    print("-" * 50)

    # ---------------------------------------------------------
    # 1. EPIC 1: Core Indexing (Member 1)
    # ---------------------------------------------------------
    print("1️⃣ Đang quét mã nguồn và tạo AST (Repository Index)...")
    # repo_index = build_repository_index(target_dir)
    
    # ---------------------------------------------------------
    # 2. EPIC 2 & 3: Knowledge Graph & AI Analysis (Member 2 & 3)
    # ---------------------------------------------------------
    print("2️⃣ Đang xây dựng Taxonomy Tree và phân tích kiến trúc...")
    # tree = build_taxonomy_tree(repo_index)
    
    # Cấu hình LLM dựa trên tham số dòng lệnh
    # llm_client = OllamaClient() if use_llm else NullLLMClient()
    
    # content_gen = ContentGenerator(repo_index, tree, summaries=[], llm=llm_client)
    # sections = content_gen.generate_all() # Trả về mảng 4 đối tượng ContentSection
    
    # ---------------------------------------------------------
    # GIAI ĐOẠN TÍCH HỢP: Mock dữ liệu (Tạm thời để test luồng CLI)
    # Xóa phần mock này khi ráp code thực tế với Member 1, 2, 3
    # ---------------------------------------------------------
    sections = [
        {
            "key": "tech", "title": "Technology Stack", 
            "body": "Mock data cho luồng tích hợp hệ thống.", 
            "facts": {"languages": ["java"], "frameworks": ["Spring Boot"]}
        },
        {
            "key": "architecture", "title": "Architecture", 
            "body": "Kiến trúc hệ thống tự động sinh.", 
            "facts": {"layers": ["API", "Service"], "layer:API": ["UserController"]}
        },
        {
            "key": "modules", "title": "Modules", 
            "body": "Danh sách các module chính.", 
            "facts": {"modules": ["billing"]}
        },
        {
            "key": "tests", "title": "Tests", 
            "body": "Cấu trúc kiểm thử của dự án.", 
            "facts": {"test_frameworks": ["JUnit"]}
        }
    ]
    # Dữ liệu index giả lập để render symbol
    repo_index = {"symbols": []} 

    # ---------------------------------------------------------
    # 3. EPIC 4: Wiki Generation (Member 4 - Phần của bạn)
    # ---------------------------------------------------------
    print("3️⃣ Đang tạo tài liệu Wiki HTML tĩnh...")
    
    # Render 4 trang chính bằng vòng lặp thay vì gọi thủ công từng hàm
    for section in sections:
        # Chuyển object ContentSection thành dictionary (nếu cần) hoặc truyền trực tiếp
        page_name = f"{section['key']}.html"
        # Hàm render_html_page này bạn sẽ cần cập nhật lại trong renderer.py 
        # để nhận dữ liệu động thay vì dữ liệu cứng.
        render_html_page(page_name, section)
        print(f"  ↳ Đã tạo {page_name}")

    print("  ↳ Đang sinh các trang chi tiết symbols...")
    render_symbol_pages(repo_index) # Cần cập nhật hàm này để nhận tham số repo_index

    print("-" * 50)
    print("✨ Phân tích hoàn tất! Mở thư mục /wiki để xem tài liệu.")

def main():
    # Khởi tạo CLI Parser
    parser = argparse.ArgumentParser(
        prog="repoatlas",
        description="RepoAtlas - Trình phân tích mã nguồn và tự động tạo tài liệu Wiki."
    )
    
    # Tạo các lệnh phụ (subcommands)
    subparsers = parser.add_subparsers(dest="command", required=True, help="Các lệnh khả dụng")
    
    # Cấu hình cho lệnh 'analyze'
    analyze_parser = subparsers.add_parser("analyze", help="Phân tích dự án và tạo wiki")
    analyze_parser.add_argument(
        "path", 
        type=str, 
        help="Đường dẫn thư mục cục bộ (local path) của dự án cần phân tích"
    )
    analyze_parser.add_argument(
        "--no-llm", 
        action="store_true", 
        help="Tắt LLM, chỉ tạo tài liệu dựa trên phân tích cấu trúc thô (nhanh hơn)"
    )

    # Phân tích tham số người dùng nhập
    args = parser.parse_args()

    # Điều hướng logic
    if args.command == "analyze":
        use_llm = not args.no_llm
        run_analysis_pipeline(args.path, use_llm)

if __name__ == "__main__":
    main()
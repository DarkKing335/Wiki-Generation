import argparse
import sys
import os
from pathlib import Path
import webbrowser

# --- Import thư viện từ Member 1 (Core Indexing) ---
from core_indexing.scanner import RepositoryScanner
from core_indexing.indexer import RepositoryIndexer
from core_indexing.ir_generator import IRGenerator

# --- Import thư viện từ Member 3 (AI Analysis) ---
from ai_analysis.__main__ import run as run_ai_analysis
from ai_analysis.__main__ import write_result as write_ai_result
from ai_analysis.llm.ollama import DEFAULT_ENDPOINT, DEFAULT_MODEL

# --- Import thư viện từ Member 2 (Knowledge Graph) ---
from knowledge_graph.builder import build_from_paths, write_graph

# --- Import thư viện từ Member 4 (Wiki Generation - Của bạn) ---
from wiki_generation.renderer import (
    render_html_page,
    render_symbol_pages,
    generate_search_index
)

class AIConfig:
    """Class cấu hình giả lập argparse.Namespace để truyền cho Member 3"""
    def __init__(self, use_llm: bool):
        self.index_dir = "indexes"
        self.output_dir = "analysis"
        self.model = DEFAULT_MODEL
        self.endpoint = DEFAULT_ENDPOINT
        self.no_llm = not use_llm
        self.taxonomy = "auto"
        self.budget = 2000
        self.no_tools = True
        self.verbose = False



def run_analysis_pipeline(target_path: str, use_llm: bool):
    target_dir = Path(target_path).resolve()
    if not target_dir.exists():
        print(f"ERROR: Khong tim thay duong dan '{target_dir}'")
        sys.exit(1)

    print(f"START: Bat dau phan tich du an tai: {target_dir}")
    print(f"AI MODE: {'ON' if use_llm else 'OFF'}")
    print("-" * 50)

    scanner = None
    try:
        # ---------------------------------------------------------
        # 1. EPIC 1: Core Indexing
        # ---------------------------------------------------------
        print("1. [Epic 1] Dang quet ma nguon va tao AST...")
        scanner = RepositoryScanner(target=str(target_dir), output_dir="indexes")
        tree, file_indexes = scanner.scan_and_parse()

        indexer = RepositoryIndexer(
            repository_name=Path(scanner.repo_path).name,
            repository_path=str(scanner.repo_path),
            directory_tree=tree,
            file_indexes=file_indexes
        )
        repo_index = indexer.build_index()

        # Member 1 ghi dữ liệu ra thư mục 'indexes/'
        generator = IRGenerator(index=repo_index, output_dir="indexes")
        generator.generate_all()

        # ---------------------------------------------------------
        # 2. EPIC 3: AI Analysis 
        # (Chạy trước Epic 2 vì Graph cần file summaries.json)
        # ---------------------------------------------------------
        print("2. [Epic 3] Dang phan tich kien truc va tao tom tat...")
        ai_args = AIConfig(use_llm)
        # Hứng đối tượng AnalysisResult từ hàm run của Member 3
        analysis_result = run_ai_analysis(ai_args) 
        
        # Member 3 ghi dữ liệu ra thư mục 'analysis/'
        write_ai_result(analysis_result, "analysis")

        # ---------------------------------------------------------
        # 3. EPIC 2: Knowledge Graph
        # ---------------------------------------------------------
        print("3. [Epic 2] Dang xay dung Knowledge Graph...")
        # Đọc từ 2 thư mục vừa tạo
        graph = build_from_paths("indexes", "analysis") 
        write_graph(graph, "graphs")

        # ---------------------------------------------------------
        # 4. EPIC 4: Wiki Generation (Phần của bạn)
        # ---------------------------------------------------------
        print("4. [Epic 4] Dang tao tai lieu Wiki HTML tinh...")

        # Phân rã dữ liệu THẬT từ biến analysis_result (truyền vào Jinja2)
        for section in analysis_result.content:
            page_name = f"{section.key}.html"
            # Ép kiểu Pydantic Model của Member 3 thành dictionary
            render_html_page(page_name, section.model_dump())
            print(f"  -> Da tao {page_name}")

        print("  -> Dang sinh cac trang chi tiet symbols...")
        # Lấy thẳng Pydantic model repo_index từ Member 1
        repo_index_dict = repo_index.model_dump()
        render_symbol_pages(repo_index_dict)

        print("  -> Dang sinh Search Index (JavaScript)...")
        generate_search_index(repo_index_dict)

        print("  -> Dang tao trang Dashboard index.html...")
        from wiki_generation.renderer import render_index_page
        render_index_page(repo_index_dict, analysis_result.model_dump())
        print("  -> Da tao index.html")

        print("-" * 50)
        print("SUCCESS: Phan tich hoan tat! Mo thu muc /wiki de xem tai lieu.")

        backend_dir = Path(__file__).resolve().parent.parent
        wiki_index_path = backend_dir / "wiki" / "index.html"        
        try:
            # Nếu là hệ điều hành Windows, dùng os.startfile (chắc chắn 100% hoạt động)
            if os.name == 'nt':
                os.startfile(wiki_index_path)
            # Nếu là Mac hoặc Linux
            else:
                webbrowser.open(wiki_index_path.as_uri())
        except Exception as e:
            print(f"WARNING: Khong the tu dong bat trinh duyet. Ban hay click dup vao file nay nhe: {wiki_index_path}")

    finally:
        # Dọn dẹp tài nguyên từ Member 1 (nếu clone git)
        if scanner:
            scanner.cleanup()

def main(argv=None):
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        prog="repoatlas",
        description="RepoAtlas - Trình phân tích mã nguồn và tự động tạo tài liệu Wiki."
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Các lệnh khả dụng")
    
    analyze_parser = subparsers.add_parser("analyze", help="Phân tích dự án và tạo wiki")
    analyze_parser.add_argument(
        "path", 
        type=str, 
        nargs="?",
        default=".",
        help="Đường dẫn thư mục dự án (Mặc định: thư mục hiện tại)"
    )
    analyze_parser.add_argument(
        "--no-llm", 
        action="store_true", 
        help="Tắt LLM, chỉ tạo tài liệu dựa trên phân tích cấu trúc thô (nhanh hơn)"
    )

    args = parser.parse_args(argv)

    if args.command == "analyze":
        use_llm = not args.no_llm
        run_analysis_pipeline(args.path, use_llm)


if __name__ == "__main__":
    main()
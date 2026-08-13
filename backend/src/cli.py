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

# Mặc định: model 1.5B nằm trọn trong 4 GB VRAM, nên nhanh hơn ~8 lần so với
# bản 7B (7B bị tràn 1/3 sang RAM CPU). Đổi bằng cờ --model nếu có GPU lớn hơn.
DEFAULT_CLI_MODEL = "qwen2.5-coder:1.5b"


class AIConfig:
    """Class cấu hình giả lập argparse.Namespace để truyền cho Member 3"""
    def __init__(self, use_llm: bool, model: str = DEFAULT_CLI_MODEL, workers: int = 2):
        self.index_dir = "indexes"
        self.output_dir = "analysis"
        self.model = model
        self.endpoint = DEFAULT_ENDPOINT
        self.no_llm = not use_llm
        self.taxonomy = "auto"
        self.budget = 2000
        self.no_tools = True
        self.workers = workers
        self.verbose = False


def run_analysis_pipeline(
    target_path: str,
    use_llm: bool,
    model: str = DEFAULT_CLI_MODEL,
    workers: int = 2,
):
    target_dir = Path(target_path).resolve()
    if not target_dir.exists():
        print(f"❌ Lỗi: Không tìm thấy đường dẫn '{target_dir}'")
        sys.exit(1)

    print(f"🚀 Bắt đầu phân tích dự án tại: {target_dir}")
    print(f"🤖 Chế độ AI (LLM): {'BẬT' if use_llm else 'TẮT'}")
    if use_llm:
        print(f"🧠 Model: {model} ({workers} worker song song)")
    print("-" * 50)

    scanner = None
    try:
        # ---------------------------------------------------------
        # 1. EPIC 1: Core Indexing
        # ---------------------------------------------------------
        print("1️⃣ [Epic 1] Đang quét mã nguồn và tạo AST...")
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
        print("2️⃣ [Epic 3] Đang phân tích kiến trúc và tạo tóm tắt...")
        ai_args = AIConfig(use_llm, model=model, workers=workers)
        # Hứng đối tượng AnalysisResult từ hàm run của Member 3
        analysis_result = run_ai_analysis(ai_args) 
        
        # Member 3 ghi dữ liệu ra thư mục 'analysis/'
        write_ai_result(analysis_result, "analysis")

        # ---------------------------------------------------------
        # 3. EPIC 2: Knowledge Graph
        # ---------------------------------------------------------
        print("3️⃣ [Epic 2] Đang xây dựng Knowledge Graph...")
        # Đọc từ 2 thư mục vừa tạo
        graph = build_from_paths("indexes", "analysis") 
        write_graph(graph, "graphs")

        # ---------------------------------------------------------
        # 4. EPIC 4: Wiki Generation (Phần của bạn)
        # ---------------------------------------------------------
        print("4️⃣ [Epic 4] Đang tạo tài liệu Wiki HTML tĩnh...")

        # Phân rã dữ liệu THẬT từ biến analysis_result (truyền vào Jinja2)
        for section in analysis_result.content:
            page_name = f"{section.key}.html"
            # Ép kiểu Pydantic Model của Member 3 thành dictionary
            render_html_page(page_name, section.model_dump())
            print(f"  ↳ Đã tạo {page_name}")

        print("  ↳ Đang sinh các trang chi tiết symbols...")
        # Lấy thẳng Pydantic model repo_index từ Member 1
        repo_index_dict = repo_index.model_dump()
        render_symbol_pages(repo_index_dict)

        print("  ↳ Đang sinh Search Index (JavaScript)...")
        generate_search_index(repo_index_dict)

        print("-" * 50)
        print("✨ Phân tích hoàn tất! Mở thư mục /wiki để xem tài liệu.")

        backend_dir = Path(__file__).resolve().parent.parent
        wiki_index_path = backend_dir / "wiki" / "architecture.html"        
        try:
            # Nếu là hệ điều hành Windows, dùng os.startfile (chắc chắn 100% hoạt động)
            if os.name == 'nt':
                os.startfile(wiki_index_path)
            # Nếu là Mac hoặc Linux
            else:
                webbrowser.open(wiki_index_path.as_uri())
        except Exception as e:
            print(f"⚠️ Không thể tự động bật trình duyệt. Bạn hãy click đúp vào file này nhé: {wiki_index_path}")

    finally:
        # Dọn dẹp tài nguyên từ Member 1 (nếu clone git)
        if scanner:
            scanner.cleanup()

def main():
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
    analyze_parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_CLI_MODEL,
        help=f"Model Ollama dùng để tóm tắt (mặc định: {DEFAULT_CLI_MODEL})"
    )
    analyze_parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help=(
            "Số node chạy song song trong cùng một tier (mặc định: 2, nhanh hơn "
            "~1.5 lần). Dùng 1 nếu cần kết quả tái lập được y hệt giữa các lần chạy"
        )
    )

    args = parser.parse_args()

    if args.command == "analyze":
        use_llm = not args.no_llm
        run_analysis_pipeline(args.path, use_llm, model=args.model, workers=args.workers)

if __name__ == "__main__":
    main()
"""Script đóng gói toàn bộ mã nguồn, cấu trúc thư mục và tài liệu của dự án Maple Leaf vào một file Markdown duy nhất."""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Thư mục gốc của dự án
PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = PROJECT_ROOT / "MAPLE_LEAF_CODEBASE.md"

# Bản đồ đuôi tệp sang ngôn ngữ Markdown syntax highlighting
LANG_MAP = {
    ".py": "python",
    ".json": "json",
    ".toml": "toml",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".sql": "sql",
    ".md": "markdown",
    ".sh": "bash",
    ".bat": "batch",
    ".ini": "ini",
    ".mako": "mako",
    ".txt": "text",
    ".in": "text",
    ".example": "text",
    ".dockerignore": "text",
    ".gitignore": "text",
    ".gitattributes": "text",
    ".editorconfig": "ini",
}


def get_git_files() -> list[str]:
    """Lấy danh sách các tệp được Git theo dõi."""
    result = subprocess.check_output(["git", "ls-files"], cwd=PROJECT_ROOT, text=True, encoding="utf-8")
    return sorted(result.splitlines())


def generate_tree(file_paths: list[str]) -> str:
    """Tạo biểu diễn cây thư mục (ASCII Tree) từ danh sách đường dẫn tệp."""
    tree: dict = {}
    for path in file_paths:
        parts = path.split("/")
        current = tree
        for part in parts:
            current = current.setdefault(part, {})

    lines: list[str] = ["Maple-Leaf/"]

    def _build_tree(node: dict, prefix: str = ""):
        items = sorted(node.keys(), key=lambda k: (len(node[k]) == 0, k.lower()))
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            child_prefix = "    " if is_last else "│   "
            lines.append(f"{prefix}{connector}{item}")
            if node[item]:
                _build_tree(node[item], prefix + child_prefix)

    _build_tree(tree)
    return "\n".join(lines)


def get_safe_fence(content: str) -> str:
    """Xác định số lượng dấu backtick an toàn để không bị vỡ Markdown code block."""
    max_ticks = 0
    current_ticks = 0
    for char in content:
        if char == "`":
            current_ticks += 1
            if current_ticks > max_ticks:
                max_ticks = current_ticks
        else:
            current_ticks = 0
    count = max(3, max_ticks + 1)
    return "`" * count


def format_file_content(rel_path: str, abs_path: Path) -> str:
    """Định dạng nội dung của một tệp thành một khối Markdown hoàn chỉnh."""
    # Xử lý tệp nhị phân (PNG, JPG, etc.)
    if abs_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".ico", ".db", ".sqlite"]:
        size_bytes = abs_path.stat().st_size
        return (
            f"### 📄 `{rel_path}`\n\n"
            f"> 🖼️ **Tệp nhị phân** ({abs_path.suffix.upper()}) | Kích thước: `{size_bytes:,}` bytes.\n"
            f"> Tệp này được lưu trữ nhị phân trong kho mã nguồn.\n\n"
            "---\n"
        )

    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        content = f"Lỗi khi đọc file: {e}"

    lines = content.splitlines()
    ext = abs_path.suffix.lower()
    lang = LANG_MAP.get(ext, "")
    if abs_path.name == "Dockerfile":
        lang = "dockerfile"
    elif abs_path.name == "LICENSE":
        lang = "text"

    fence = get_safe_fence(content)
    line_count = len(lines)
    size_bytes = len(content.encode("utf-8"))

    return (
        f"### 📄 `{rel_path}`\n\n"
        f"- **Đường dẫn:** `{rel_path}`\n"
        f"- **Số dòng:** `{line_count:,}` dòng | **Kích thước:** `{size_bytes:,}` bytes | **Ngôn ngữ:** `{lang or 'text'}`\n\n"
        f"{fence}{lang}\n"
        f"{content}\n"
        f"{fence}\n\n"
        "---\n"
    )


def categorize_files(files: list[str]) -> dict[str, list[str]]:
    """Phân loại tệp vào các nhóm chức năng rõ ràng."""
    categories: dict[str, list[str]] = {
        "1. Cấu hình & Môi trường dự án (Root configs & Build scripts)": [],
        "2. Điểm khởi chạy & Cấu hình cốt lõi (`app/main.py`, `app/config.py`)": [],
        "3. Bot Client & Quản lý vòng đời (`app/bot/`)": [],
        "4. Bảo mật & Mã hóa Cookie (`app/security/`)": [],
        "5. Cơ sở dữ liệu SQLite & Repository Pattern (`app/db/`)": [],
        "6. Dữ liệu trò chơi Genshin Impact & Honkai: Star Rail (`app/games/`)": [],
        "7. Tích hợp API bên ngoài Enka & Cache (`app/integrations/`)": [],
        "8. Dịch vụ nghiệp vụ Business Services (`app/services/`)": [],
        "9. Hệ thống tự động hóa tác vụ Background Automation (`app/automation/`)": [],
        "10. Discord Slash Commands Cogs (`app/commands/`)": [],
        "11. Giao diện Discord UI Buttons & Views (`app/ui/`)": [],
        "12. Đồ họa & Render thẻ Pillow Cards (`app/render/`)": [],
        "13. Tiện ích & Hỗ trợ đa ngôn ngữ (`app/utils/`)": [],
        "14. Triển khai Render & PostgreSQL Migration (`deploy/`)": [],
        "15. Kịch bản tiện ích hỗ trợ (`scripts/`)": [],
        "16. Bộ kiểm thử tự động Unit Tests (`tests/`)": [],
        "17. Tài liệu hướng dẫn & Kiến trúc (`docs/`, `README.md`)": [],
        "18. Tài nguyên hình ảnh tĩnh (`assets/`)": [],
    }

    for f in files:
        if f.startswith("assets/"):
            categories["18. Tài nguyên hình ảnh tĩnh (`assets/`)"].append(f)
        elif f.startswith("tests/"):
            categories["16. Bộ kiểm thử tự động Unit Tests (`tests/`)"].append(f)
        elif f.startswith("scripts/"):
            categories["15. Kịch bản tiện ích hỗ trợ (`scripts/`)"].append(f)
        elif f.startswith("deploy/"):
            categories["14. Triển khai Render & PostgreSQL Migration (`deploy/`)"].append(f)
        elif f.startswith("docs/") or f in ["README.md", "README.en.md", "CONTRIBUTING.md", "CHANGELOG.md", "SECURITY.md", "LICENSE"]:
            categories["17. Tài liệu hướng dẫn & Kiến trúc (`docs/`, `README.md`)"].append(f)
        elif f in ["app/main.py", "app/config.py", "app/__init__.py"]:
            categories["2. Điểm khởi chạy & Cấu hình cốt lõi (`app/main.py`, `app/config.py`)"].append(f)
        elif f.startswith("app/bot/"):
            categories["3. Bot Client & Quản lý vòng đời (`app/bot/`)"].append(f)
        elif f.startswith("app/security/"):
            categories["4. Bảo mật & Mã hóa Cookie (`app/security/`)"].append(f)
        elif f.startswith("app/db/"):
            categories["5. Cơ sở dữ liệu SQLite & Repository Pattern (`app/db/`)"].append(f)
        elif f.startswith("app/games/"):
            categories["6. Dữ liệu trò chơi Genshin Impact & Honkai: Star Rail (`app/games/`)"].append(f)
        elif f.startswith("app/integrations/"):
            categories["7. Tích hợp API bên ngoài Enka & Cache (`app/integrations/`)"].append(f)
        elif f.startswith("app/services/"):
            categories["8. Dịch vụ nghiệp vụ Business Services (`app/services/`)"].append(f)
        elif f.startswith("app/automation/"):
            categories["9. Hệ thống tự động hóa tác vụ Background Automation (`app/automation/`)"].append(f)
        elif f.startswith("app/commands/"):
            categories["10. Discord Slash Commands Cogs (`app/commands/`)"].append(f)
        elif f.startswith("app/ui/"):
            categories["11. Giao diện Discord UI Buttons & Views (`app/ui/`)"].append(f)
        elif f.startswith("app/render/"):
            categories["12. Đồ họa & Render thẻ Pillow Cards (`app/render/`)"].append(f)
        elif f.startswith("app/utils/"):
            categories["13. Tiện ích & Hỗ trợ đa ngôn ngữ (`app/utils/`)"].append(f)
        else:
            categories["1. Cấu hình & Môi trường dự án (Root configs & Build scripts)"].append(f)

    return categories


def main():
    print("🍁 Đang bắt đầu thu thập mã nguồn dự án Maple Leaf...")
    files = get_git_files()
    categorized = categorize_files(files)

    total_files = len(files)
    tree_text = generate_tree(files)

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Xây dựng phần đầu tài liệu
    doc_parts: list[str] = [
        "# 🍁 MAPLE LEAF - TOÀN BỘ MÃ NGUỒN VÀ CẤU TRÚC DỰ ÁN",
        "",
        "> **Tên dự án:** Maple Leaf (Trợ thủ Discord cho Genshin Impact & Honkai: Star Rail)  ",
        f"> **Thời điểm tạo tài liệu:** `{now_str}`  ",
        f"> **Tổng số tệp được đóng gói:** `{total_files}` tệp tin  ",
        "> **Ngôn ngữ chính:** Python 3.12 (Asynchronous `asyncio`) | **Thư viện chính:** `discord.py 2.4.x`, `Pillow`, `APScheduler`, `aiohttp`, `aiosqlite`, `asyncpg`, `pydantic`  ",
        "> **Bảo mật:** Tệp `.env` chứa thông tin nhạy cảm (token bot thực tế) được chủ động loại trừ theo chuẩn bảo mật; tệp `.env.example` và hướng dẫn cấu hình đầy đủ được đính kèm bên dưới.  ",
        "",
        "---",
        "",
        "## 📑 MỤC LỤC TỔNG QUAN",
        "",
        "1. [Cấu Trúc Thư Mục Dự Án (Project Tree)](#1-cấu-trúc-thư-mục-dự-án)",
    ]

    # Thêm mục lục phân nhóm
    section_index = 2
    for cat_name, flist in categorized.items():
        if flist:
            anchor = cat_name.lower().replace(" ", "-").replace("`", "").replace("(", "").replace(")", "").replace("/", "").replace(":", "")
            doc_parts.append(f"{section_index}. [{cat_name} ({len(flist)} tệp)](#{anchor})")
            section_index += 1

    doc_parts.extend([
        "",
        "---",
        "",
        "## 1. Cấu Trúc Thư Mục Dự Án",
        "",
        "Biểu đồ cây toàn bộ thư mục và tệp tin trong repository:",
        "",
        "```text",
        tree_text,
        "```",
        "",
        "---",
        "",
    ])

    # Thêm từng nhóm và nội dung tệp
    for cat_name, flist in categorized.items():
        if not flist:
            continue
        anchor_id = cat_name.lower().replace(" ", "-").replace("`", "").replace("(", "").replace(")", "").replace("/", "").replace(":", "")
        doc_parts.extend([
            f"## <a id=\"{anchor_id}\"></a>{cat_name}",
            "",
            f"> Nhóm này chứa **{len(flist)}** tệp tin.",
            "",
        ])

        for rel_path in flist:
            abs_path = PROJECT_ROOT / rel_path
            doc_parts.append(format_file_content(rel_path, abs_path))

    # Ghi ra tệp Markdown
    print(f"🍁 Đang ghi toàn bộ nội dung ra: {OUTPUT_FILE}...")
    full_markdown = "\n".join(doc_parts)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(full_markdown)

    size_mb = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    line_count = len(full_markdown.splitlines())
    print(f"✅ Hoàn thành đóng gói! Tệp: {OUTPUT_FILE}")
    print(f"📊 Thống kê: {total_files} tệp | {line_count:,} dòng Markdown | {size_mb:.2f} MB")


if __name__ == "__main__":
    main()

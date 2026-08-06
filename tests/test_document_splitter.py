"""DocumentSplitterService 单元测试（纯逻辑，不依赖 Milvus / LLM）"""

from app.services.document_splitter_service import document_splitter_service


def test_split_markdown_adds_source_metadata():
    content = """# 标题一

第一章内容，用来验证按标题拆分是否生效，确保分片携带来源信息。

## 子标题

子章节内容，用于验证二级标题。

# 标题二

第二章内容，用于验证多个一级标题分别成片。
"""
    docs = document_splitter_service.split_markdown(content, file_path="docs/example.md")

    assert docs, "应该至少切出一个分片"
    for doc in docs:
        assert doc.metadata["_source"] == "docs/example.md"
        assert doc.metadata["_file_name"] == "example.md"
        assert doc.metadata["_extension"] == ".md"

    joined = "\n".join(d.page_content for d in docs)
    assert "标题一" in joined
    assert "标题二" in joined


def test_split_empty_content_returns_empty_list():
    assert document_splitter_service.split_markdown("", "a.md") == []
    assert document_splitter_service.split_markdown("   \n\t ", "b.md") == []


def test_small_chunks_are_merged():
    content = (
        "# 大段内容\n\n" + "这是用来占满一个分片的正常内容。" * 30
        + "\n\n# 小段\n\n很短的一句话。"
    )
    docs = document_splitter_service.split_markdown(content, "docs/merge.md")

    assert docs, "大段内容应至少产生一个分片"
    # 小分片不应单独存在：任何分片长度都应大于小段的长度
    for doc in docs:
        assert len(doc.page_content) > 10


def test_split_plain_text():
    content = ("这是第一行测试内容，用于验证普通文本分割。\n" * 30)
    docs = document_splitter_service.split_text(content, "docs/plain.txt")

    assert docs
    assert docs[0].metadata["_extension"] == ".txt"
    assert docs[0].metadata["_file_name"] == "plain.txt"

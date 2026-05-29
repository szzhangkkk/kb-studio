"""Export functionality - KB export as ZIP, Markdown reports."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime
from pathlib import Path


class KBExporter:
    """Export knowledge bases in various formats."""

    def __init__(self, data_dir: str = "./data"):
        self._data_dir = Path(data_dir)

    def export_kb_zip(self, kb_name: str) -> bytes:
        """Export a knowledge base as a ZIP package.

        Includes: documents, config, chunks, memory, findings.
        """
        kb_dir = self._data_dir / kb_name
        if not kb_dir.exists():
            raise FileNotFoundError(f"Knowledge base '{kb_name}' not found")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add metadata
            meta = {
                "kb_name": kb_name,
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "version": "0.1.0",
            }
            zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

            # Add all files from KB directory
            for file_path in sorted(kb_dir.rglob("*")):
                if file_path.is_file():
                    arcname = str(file_path.relative_to(kb_dir))
                    zf.write(file_path, arcname)

        return buf.getvalue()

    def export_kb_markdown(self, kb_name: str) -> str:
        """Export a knowledge base as a single Markdown document."""
        kb_dir = self._data_dir / kb_name
        if not kb_dir.exists():
            raise FileNotFoundError(f"Knowledge base '{kb_name}' not found")

        lines = [
            f"# {kb_name}",
            "",
            f"导出时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
            "---",
            "",
        ]

        # Read config
        config_path = kb_dir / "config.yaml"
        if config_path.exists():
            lines.append("## 配置")
            lines.append("")
            lines.append("```yaml")
            lines.append(config_path.read_text(encoding="utf-8").strip())
            lines.append("```")
            lines.append("")

        # Read documents
        docs_dir = kb_dir / "docs"
        if docs_dir.exists():
            doc_files = sorted(docs_dir.glob("*.md"))
            if doc_files:
                lines.append(f"## 文档 ({len(doc_files)} 篇)")
                lines.append("")
                for doc_file in doc_files:
                    lines.append(f"### {doc_file.stem}")
                    lines.append("")
                    content = doc_file.read_text(encoding="utf-8")
                    lines.append(content)
                    lines.append("")
                    lines.append("---")
                    lines.append("")

        # Read memory
        memory_path = kb_dir / "memory.json"
        if memory_path.exists():
            try:
                memory = json.loads(memory_path.read_text())
                entries = memory.get("entries", [])
                if entries:
                    lines.append(f"## 记忆 ({len(entries)} 条)")
                    lines.append("")
                    for entry in entries:
                        cat = entry.get("category", "general")
                        content = entry.get("content", "")
                        importance = entry.get("importance", "medium")
                        lines.append(f"- **[{cat}]** ({importance}) {content}")
                    lines.append("")
            except Exception:
                pass

        # Read findings
        findings_path = kb_dir / "findings.json"
        if findings_path.exists():
            try:
                findings = json.loads(findings_path.read_text())
                if findings:
                    open_findings = [f for f in findings if f.get("status") == "open"]
                    lines.append(f"## 质量检查 ({len(open_findings)} 个待处理)")
                    lines.append("")
                    for f in findings:
                        status = f.get("status", "open")
                        ftype = f.get("type", "unknown")
                        explanation = f.get("explanation", "")
                        icon = {"contradiction": "!", "duplicate": "=", "update": "~"}.get(ftype, "?")
                        lines.append(f"- [{status}] **{ftype}** {icon} {explanation}")
                    lines.append("")
            except Exception:
                pass

        return "\n".join(lines)

    def export_all_zip(self) -> bytes:
        """Export all knowledge bases as a single ZIP."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            meta = {
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "version": "0.1.0",
                "type": "full_export",
            }
            zf.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

            for kb_dir in sorted(self._data_dir.iterdir()):
                if kb_dir.is_dir() and kb_dir.name not in ("scheduler", "tools"):
                    for file_path in sorted(kb_dir.rglob("*")):
                        if file_path.is_file():
                            arcname = f"{kb_dir.name}/{file_path.relative_to(kb_dir)}"
                            zf.write(file_path, arcname)

        return buf.getvalue()

    def export_findings_report(self, kb_name: str) -> str:
        """Generate a Markdown quality report for a KB."""
        kb_dir = self._data_dir / kb_name
        findings_path = kb_dir / "findings.json"

        lines = [
            f"# 质量检查报告: {kb_name}",
            "",
            f"生成时间: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
        ]

        if not findings_path.exists():
            lines.append("暂无质量检查数据。")
            return "\n".join(lines)

        try:
            findings = json.loads(findings_path.read_text())
        except Exception:
            lines.append("读取数据失败。")
            return "\n".join(lines)

        if not findings:
            lines.append("未发现问题，知识库状态良好。")
            return "\n".join(lines)

        # Summary
        by_type = {}
        by_status = {}
        for f in findings:
            t = f.get("type", "unknown")
            s = f.get("status", "open")
            by_type[t] = by_type.get(t, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1

        lines.append("## 概览")
        lines.append("")
        lines.append(f"- 总问题数: {len(findings)}")
        for t, count in by_type.items():
            label = {"contradiction": "矛盾", "duplicate": "重复", "update": "需更新"}.get(t, t)
            lines.append(f"- {label}: {count}")
        lines.append("")

        # Detail table
        lines.append("## 详细列表")
        lines.append("")
        lines.append("| 类型 | 状态 | 说明 | 来源1 | 来源2 |")
        lines.append("|------|------|------|-------|-------|")

        for f in findings:
            ftype = {"contradiction": "矛盾", "duplicate": "重复", "update": "需更新"}.get(f.get("type", ""), "?")
            status = {"open": "待处理", "resolved": "已解决", "dismissed": "已忽略"}.get(f.get("status", ""), "?")
            explanation = f.get("explanation", "")[:50]
            src1 = f.get("new_chunk", {}).get("source", "")[:20]
            src2 = f.get("existing_chunk", {}).get("source", "")[:20]
            lines.append(f"| {ftype} | {status} | {explanation} | {src1} | {src2} |")

        return "\n".join(lines)

    def import_kb_zip(self, zip_data: bytes, rename_to: str | None = None) -> dict:
        """Import a knowledge base from a ZIP package.
        Returns: { "kb_name": str, "doc_count": int, "chunk_count": int }
        """
        buf = io.BytesIO(zip_data)
        with zipfile.ZipFile(buf, "r") as zf:
            meta = {}
            if "meta.json" in zf.namelist():
                meta = json.loads(zf.read("meta.json"))

            kb_name = rename_to or meta.get("kb_name", "imported")
            target_dir = self._data_dir / kb_name

            if target_dir.exists() and not rename_to:
                i = 1
                while (self._data_dir / f"{kb_name}_{i}").exists():
                    i += 1
                kb_name = f"{kb_name}_{i}"
                target_dir = self._data_dir / kb_name

            target_dir.mkdir(parents=True, exist_ok=True)

            for name in zf.namelist():
                if name == "meta.json":
                    continue
                if name.endswith("/"):
                    (target_dir / name).mkdir(parents=True, exist_ok=True)
                    continue
                safe_path = target_dir / name
                if not str(safe_path.resolve()).startswith(str(target_dir.resolve())):
                    continue
                safe_path.parent.mkdir(parents=True, exist_ok=True)
                safe_path.write_bytes(zf.read(name))

            doc_count = 0
            chunk_count = 0
            docs_json = target_dir / "documents.json"
            if docs_json.exists():
                try:
                    doc_count = len(json.loads(docs_json.read_text()))
                except Exception:
                    pass
            chunks_json = target_dir / "chunks.json"
            if chunks_json.exists():
                try:
                    chunk_count = len(json.loads(chunks_json.read_text()))
                except Exception:
                    pass

            return {"kb_name": kb_name, "doc_count": doc_count, "chunk_count": chunk_count}

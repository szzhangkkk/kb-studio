"""Multi-agent pipeline for KB-Studio."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class PipelineStep:
    name: str
    role_prompt: str = ""
    kb_names: list[str] = field(default_factory=list)
    top_k: int = 5
    enabled: bool = True


class AgentPipeline:
    """Executes a chain of agents: retriever → analyzer → generator → reviewer."""

    def __init__(self, llm_client, engines: dict):
        self.llm = llm_client
        self.engines = engines  # kb_name -> ChatEngine

    def run(self, question: str, steps: list[dict], memory_context: str = "") -> dict:
        """Run the pipeline with the given steps."""
        start = time.time()
        context: dict = {"question": question, "steps_log": []}

        for step_cfg in steps:
            step = PipelineStep(**step_cfg) if isinstance(step_cfg, dict) else step_cfg
            if not step.enabled:
                continue

            step_start = time.time()
            step_log = {"name": step.name, "status": "ok"}

            try:
                if step.name == "retriever":
                    context["retrieval"] = self._run_retriever(question, step)
                    step_log["output_preview"] = f"{len(context['retrieval'])} chunks retrieved"
                elif step.name == "analyzer":
                    context["analysis"] = self._run_analyzer(question, context, step)
                    step_log["output_preview"] = context["analysis"][:200]
                elif step.name == "generator":
                    context["answer"] = self._run_generator(question, context, step, memory_context)
                    step_log["output_preview"] = context["answer"][:200]
                elif step.name == "reviewer":
                    context["review"] = self._run_reviewer(question, context, step)
                    step_log["output_preview"] = context["review"][:200]
                else:
                    step_log["status"] = "skipped"
                    step_log["output_preview"] = f"Unknown step: {step.name}"
            except Exception as e:
                step_log["status"] = "error"
                step_log["output_preview"] = str(e)

            step_log["latency"] = round(time.time() - step_start, 3)
            context["steps_log"].append(step_log)

        # Collect all sources
        all_sources = set()
        for r in context.get("retrieval", []):
            all_sources.add(r.get("source", ""))

        return {
            "answer": context.get("answer", ""),
            "analysis": context.get("analysis", ""),
            "review": context.get("review", ""),
            "sources": list(all_sources),
            "retrieval_results": context.get("retrieval", []),
            "steps_log": context.get("steps_log", []),
            "latency": round(time.time() - start, 3),
        }

    def _run_retriever(self, question: str, step: PipelineStep) -> list[dict]:
        """Retrieve from one or more KBs and merge results."""
        all_results = []
        for kb_name in step.kb_names:
            engine = self.engines.get(kb_name)
            if engine:
                result = engine.search(question, top_k=step.top_k)
                all_results.extend(result.get("results", []))

        all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return all_results[:step.top_k]

    def _run_analyzer(self, question: str, context: dict, step: PipelineStep) -> str:
        """Analyze retrieval results."""
        chunks = context.get("retrieval", [])
        chunks_text = "\n\n---\n\n".join([r["content"] for r in chunks]) if chunks else "无检索结果"

        messages = [
            {"role": "system", "content": step.role_prompt or "你是信息分析专家，负责从检索结果中提取关键信息和洞察。"},
            {"role": "user", "content": f"问题：{question}\n\n检索到的文档片段：\n{chunks_text}\n\n请分析以上内容，提取与问题相关的关键信息。"},
        ]
        return self.llm.chat_text(messages=messages, temperature=0.3)

    def _run_generator(self, question: str, context: dict, step: PipelineStep,
                       memory_context: str = "") -> str:
        """Generate the final answer."""
        analysis = context.get("analysis", "")
        retrieval = context.get("retrieval", [])
        ref_text = "\n\n---\n\n".join([r["content"] for r in retrieval]) if retrieval else ""

        system = step.role_prompt or "你是回答生成专家，基于分析结果生成准确、有条理的回答。"
        if memory_context:
            system = f"{system}\n\n知识库记忆：\n{memory_context}"

        user_content = f"问题：{question}"
        if analysis:
            user_content = f"分析结果：\n{analysis}\n\n{user_content}"
        if ref_text:
            user_content = f"{user_content}\n\n参考文档：\n{ref_text}"

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        return self.llm.chat_text(messages=messages)

    def _run_reviewer(self, question: str, context: dict, step: PipelineStep) -> str:
        """Review the generated answer."""
        answer = context.get("answer", "")

        messages = [
            {"role": "system", "content": step.role_prompt or "你是质量审核专家，检查回答的准确性、完整性和逻辑性。如有问题请指出具体问题。如果回答质量良好，请确认OK。"},
            {"role": "user", "content": f"问题：{question}\n\n回答：\n{answer}\n\n请审核以上回答的质量。"},
        ]
        return self.llm.chat_text(messages=messages, temperature=0.3)

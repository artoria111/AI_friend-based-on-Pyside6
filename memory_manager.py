"""
Three-layer memory system for the AI pet:

Layer 1 — Working Memory:    recent 20 chat turns, always in LLM context (managed in pet_window)
Layer 2 — Semantic Memory:   explicit [MEMO] facts like "用户喜欢喝红茶" (this module)
Layer 3 — Episodic Memory:   auto-summarized chat episodes like "用户上周在调试Python" (this module)

Uses ChromaDB for vector storage. Embeddings via ModelScope (China-accessible).
"""

import hashlib
import os
from datetime import datetime

import chromadb

MODELSCOPE_MODEL = "iic/nlp_gte_sentence-embedding_chinese-small"

SUMMARY_PROMPT = (
    "你是一个记忆摘要助手。请用一两句话总结以下对话中关于「用户」的重要信息。\n"
    "重点记录：用户在做什么、心情如何、遇到了什么问题、有什么计划或决定。\n"
    "不要总结角色的回复，只总结关于用户的信息。输出一句中文（25字以内）。\n\n"
    "对话：\n{conversation}\n\n摘要："
)


class MemoryManager:
    def __init__(self, llm_client=None, llm_config=None, retrieval_k=3,
                 llm_mode="api", embed_mode="local", summary_interval=5):
        self.retrieval_k = retrieval_k
        self.llm_client = llm_client
        self.llm_config = llm_config or {}
        self.llm_mode = llm_mode
        self.embed_mode = embed_mode
        self.summary_interval = summary_interval
        self._local_model = None

        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pet_chroma_db")
        self.chroma_client = chromadb.PersistentClient(path=db_path)

        # Layer 2: semantic facts
        self.facts = self.chroma_client.get_or_create_collection(
            name="pet_facts",
            metadata={"hnsw:space": "cosine"}
        )
        # Layer 3: chat episode summaries
        self.episodes = self.chroma_client.get_or_create_collection(
            name="pet_episodes",
            metadata={"hnsw:space": "cosine"}
        )

        if embed_mode == "api" and llm_client:
            print(f"[Memory] 三层记忆就绪 (API), 事实:{self.facts.count()} 情节:{self.episodes.count()}")
        else:
            self._load_local_model()
            print(f"[Memory] 三层记忆就绪 (local, 512d), 事实:{self.facts.count()} 情节:{self.episodes.count()}")

    # ── embedding helpers ────────────────────────────────────────────

    def _load_local_model(self):
        from sentence_transformers import SentenceTransformer
        model_path = self._get_or_download_model()
        self._local_model = SentenceTransformer(model_path)
        self.embed_mode = "local"

    def _get_or_download_model(self) -> str:
        for variant in [
            MODELSCOPE_MODEL.replace("/", "--"),
            MODELSCOPE_MODEL,
        ]:
            d = os.path.join(os.path.expanduser("~"), ".cache", "modelscope", "hub", "models", variant)
            if os.path.isdir(d) and os.path.isfile(os.path.join(d, "pytorch_model.bin")):
                return d

        try:
            from modelscope import snapshot_download
            print("[Memory] 正在从 ModelScope 下载 embedding 模型 (~57MB)...")
            return snapshot_download(MODELSCOPE_MODEL)
        except Exception:
            pass

        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        from sentence_transformers import SentenceTransformer
        self._local_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self.embed_mode = "local"
        raise RuntimeError("_already_loaded")

    def _embed(self, text: str) -> list[float]:
        if self.embed_mode == "api" and self.llm_client:
            return self._embed_api(text)
        elif self._local_model:
            return self._local_model.encode(text).tolist()
        raise RuntimeError("No embedding backend available")

    def _embed_api(self, text: str) -> list[float]:
        resp = self.llm_client.embeddings.create(
            model=self.llm_config.get("embed_model", "BAAI/bge-m3"),
            input=text
        )
        return resp.data[0].embedding

    def _retrieve_from(self, query: str, collection, k: int) -> list[str]:
        if collection.count() == 0:
            return []
        q_emb = self._embed(query)
        results = collection.query(
            query_embeddings=[q_emb],
            n_results=min(k, collection.count())
        )
        docs = results.get("documents", [[]])[0]
        return [d for d in docs if d and d.strip()]

    # ── Layer 2: semantic facts ──────────────────────────────────────

    def add_fact(self, content: str, metadata: dict = None):
        metadata = metadata or {}
        metadata.setdefault("timestamp", datetime.now().isoformat())
        metadata.setdefault("type", "fact")
        embedding = self._embed(content)
        mem_id = hashlib.md5(content.encode("utf-8")).hexdigest()[:16]
        self.facts.upsert(
            ids=[mem_id], embeddings=[embedding],
            documents=[content], metadatas=[metadata]
        )

    # ── Layer 3: episodic summaries ──────────────────────────────────

    def summarize_and_store(self, recent_messages: list):
        """Summarize a block of recent conversation and store as episodic memory."""
        if not self.llm_client or len(recent_messages) < 2:
            return

        conversation = "\n".join(
            f"{'用户' if m['role'] == 'user' else '角色'}：{m['content']}"
            for m in recent_messages
            if m.get("role") in ("user", "assistant")
        )
        if not conversation.strip():
            return

        prompt = SUMMARY_PROMPT.format(conversation=conversation)

        try:
            if self.llm_mode == "api":
                resp = self.llm_client.chat.completions.create(
                    model=self.llm_config.get("api_model", ""),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.4, max_tokens=80
                )
                summary = resp.choices[0].message.content.strip()
            else:
                resp = self.llm_client.create_chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=80, temperature=0.4
                )
                summary = resp["choices"][0]["message"]["content"].strip()

            if summary and len(summary) > 3:
                self._store_episode(summary)
                print(f"[Memory] 情节摘要已存储: {summary}")
        except Exception as e:
            print(f"[Memory] 情节摘要失败: {e}")

    def _store_episode(self, content: str):
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "type": "episode"
        }
        embedding = self._embed(content)
        ep_id = hashlib.md5((content + datetime.now().isoformat()).encode()).hexdigest()[:16]
        self.episodes.upsert(
            ids=[ep_id], embeddings=[embedding],
            documents=[content], metadatas=[metadata]
        )

    # ── unified retrieval ───────────────────────────────────────────

    def retrieve_all(self, query: str) -> dict:
        """Retrieve relevant memories from both semantic and episodic layers."""
        return {
            "facts": self._retrieve_from(query, self.facts, self.retrieval_k),
            "episodes": self._retrieve_from(query, self.episodes, max(self.retrieval_k - 1, 1))
        }

    # ── formatting ──────────────────────────────────────────────────

    def format_context(self, retrieval: dict) -> str:
        """Format retrieval results for injection into LLM system prompt."""
        parts = []
        if retrieval.get("facts"):
            parts.append("[关于主人的已知信息，请自然地融入回复]")
            for i, m in enumerate(retrieval["facts"], 1):
                parts.append(f"{i}. {m}")
        if retrieval.get("episodes"):
            parts.append("[关于主人的过往回忆]")
            for i, m in enumerate(retrieval["episodes"], 1):
                parts.append(f"{i}. {m}")
        return "\n".join(parts) if parts else ""

    # ── housekeeping ────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "facts": self.facts.count(),
            "episodes": self.episodes.count()
        }

    def clear_all(self):
        for col in [self.facts, self.episodes]:
            count = col.count()
            if count > 0:
                col.delete(ids=col.get()["ids"])
        print("[Memory] 已清空所有记忆层")

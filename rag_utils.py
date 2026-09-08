from langchain_core.documents import Document


class HybridReranker:
    """
    多路检索结果混合重排器。

    支持两种融合方法：
    - "weighted": 加权分数融合（min-max 归一化后按权重相加）
    - "rrf":      Reciprocal Rank Fusion（按排名倒数求和，无参数）

    入参格式: list[tuple[Document, float]] — [(文档, 原始分数), ...]
    返回格式: list[Document] — 按最终分数降序的 top-k 文档
    """

    def __init__(
        self,
        method: str = "weighted",
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
        rrf_k: int = 60,
    ):
        if method not in ("weighted", "rrf"):
            raise ValueError(f"不支持的融合方法: {method}，可选: weighted, rrf")
        self.method = method
        self.rrf_k = rrf_k

        total = vector_weight + bm25_weight
        if total <= 0:
            raise ValueError("权重之和必须大于 0")
        self.vector_weight = vector_weight / total
        self.bm25_weight = bm25_weight / total

    def rerank(
        self,
        vector_results: list[tuple[Document, float]],
        bm25_results: list[tuple[Document, float]],
        top_k: int = 3,
    ) -> list[Document]:
        if not vector_results and not bm25_results:
            return []
        if not vector_results:
            return [doc for doc, _ in bm25_results[:top_k]]
        if not bm25_results:
            return [doc for doc, _ in vector_results[:top_k]]

        if self.method == "weighted":
            return self._weighted_fusion(vector_results, bm25_results, top_k)
        else:
            return self._rrf_fusion(vector_results, bm25_results, top_k)

    def _weighted_fusion(
        self,
        vector_results: list[tuple[Document, float]],
        bm25_results: list[tuple[Document, float]],
        top_k: int,
    ) -> list[Document]:
        vector_map = {doc.page_content: score for doc, score in vector_results}
        bm25_map = {doc.page_content: score for doc, score in bm25_results}

        all_contents = set(vector_map.keys()) | set(bm25_map.keys())

        doc_map = {}
        for doc, _ in vector_results:
            doc_map[doc.page_content] = doc
        for doc, _ in bm25_results:
            if doc.page_content not in doc_map:
                doc_map[doc.page_content] = doc

        norm_vector = self._min_max(vector_map)
        norm_bm25 = self._min_max(bm25_map)

        scored = []
        for content in all_contents:
            v = norm_vector.get(content, 0.0)
            b = norm_bm25.get(content, 0.0)
            final = self.vector_weight * v + self.bm25_weight * b
            scored.append((doc_map[content], final))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored[:top_k]]

    def _rrf_fusion(
        self,
        vector_results: list[tuple[Document, float]],
        bm25_results: list[tuple[Document, float]],
        top_k: int,
    ) -> list[Document]:
        doc_map = {}
        for doc, _ in vector_results:
            doc_map[doc.page_content] = doc
        for doc, _ in bm25_results:
            if doc.page_content not in doc_map:
                doc_map[doc.page_content] = doc

        scores: dict[str, float] = {}

        for rank, (doc, _) in enumerate(vector_results):
            scores[doc.page_content] = scores.get(doc.page_content, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        for rank, (doc, _) in enumerate(bm25_results):
            scores[doc.page_content] = scores.get(doc.page_content, 0.0) + 1.0 / (self.rrf_k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [doc_map[content] for content, _ in ranked[:top_k]]

    @staticmethod
    def _min_max(score_map: dict[str, float]) -> dict[str, float]:
        if not score_map:
            return {}
        values = list(score_map.values())
        mn, mx = min(values), max(values)
        if mx == mn:
            return {k: 0.5 for k in score_map}
        return {k: (v - mn) / (mx - mn) for k, v in score_map.items()}

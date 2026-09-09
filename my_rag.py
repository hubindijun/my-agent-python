"""
MyRag — RAG 问答主类。

编排 Chroma 向量检索 + MyChat LLM 调用，外层包 with_fallback 实现降级兜底。
LLM 调用本身通过 MyChat 的 @with_llm_retry 装饰器做 3 次指数退避重试。
"""

import logging

from dotenv import load_dotenv
load_dotenv()

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from my_chat import MyChat
from exceptions import (
    RetrieverError,
    VectorStoreInitError,
    EmbeddingModelError,
)
from retry_utils import with_fallback, with_fallback_stream, FALLBACK_MESSAGE

logger = logging.getLogger(__name__)


class MyRag:

    def __init__(self):
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name="BAAI/bge-small-zh-v1.5",
                cache_folder="./embeddings/"
            )
        except Exception as e:
            raise EmbeddingModelError(detail=str(e)) from e

        try:
            self.vectorstore = Chroma(
                persist_directory="./chroma_db",
                embedding_function=self.embeddings
            )
        except Exception as e:
            raise VectorStoreInitError(detail=str(e)) from e

        self.retriever = (
            self.vectorstore
            .as_retriever(
                search_type="similarity_score_threshold",
                search_kwargs={
                    "k": 2,
                    "score_threshold": 0.3,
                }
            )
        )

        self.chat = MyChat()

    def _retrieve(self, question: str) -> str:
        try:
            docs = self.retriever.invoke(question)
        except Exception as e:
            raise RetrieverError(message="向量检索失败", detail=str(e)) from e
        return "\n".join([doc.page_content for doc in docs])

    def query(self, question: str, model: str | None = None):
        context = self._retrieve(question)

        answer, is_fallback = with_fallback(
            lambda: self.chat.rag_chat(query=question, context=context, model=model)
        )
        return answer, is_fallback

    def query_stream(self, question: str, history: list = None, model: str | None = None):
        context = self._retrieve(question)

        stream_iter, is_fallback = with_fallback_stream(
            lambda: self.chat.rag_chat_stream(query=question, context=context, history=history, model=model)
        )
        return stream_iter, is_fallback

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
                search_kwargs={
                    "k": 2
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

    def query(self, question: str):
        context = self._retrieve(question)

        answer, is_fallback = with_fallback(
            lambda: self.chat.rag_chat(query=question, context=context)
        )
        return answer, is_fallback

    def query_stream(self, question: str, history: list = None):
        context = self._retrieve(question)

        stream_iter, is_fallback = with_fallback_stream(
            lambda: self.chat.rag_chat_stream(query=question, context=context, history=history)
        )
        return stream_iter, is_fallback

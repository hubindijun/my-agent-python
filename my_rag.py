from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

from my_chat import MyChat


class MyRag:

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            cache_folder="./embeddings/"
        )

        self.vectorstore = Chroma(
            persist_directory="./chroma_db",
            embedding_function=self.embeddings
        )

        self.retriever = (
            self.vectorstore
            .as_retriever(
                search_kwargs={
                    "k": 2
                }
            )
        )

        self.chat = MyChat()

    def query(self, question: str):
        docs = self.retriever.invoke(question)
        context = "\n".join([doc.page_content for doc in docs])
        return self.chat.rag_chat(query=question, context=context)

    def query_stream(self, question: str, history: list = None):
        """流式返回，带历史记忆"""
        docs = self.retriever.invoke(question)
        context = "\n".join([doc.page_content for doc in docs])
        return self.chat.rag_chat_stream(query=question, context=context, history=history)

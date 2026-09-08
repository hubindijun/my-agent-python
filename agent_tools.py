from langchain_core.tools import BaseTool
from langchain_core.tools import tool

from my_rag import MyRag
from exceptions import RetrieverError


def make_rag_retrieval_tool(rag: MyRag) -> BaseTool:
    """将 MyRag._retrieve 包装为 LangChain 工具（备用，当前 RAG 是图节点不是 tool）。"""

    @tool
    def rag_retrieve(query: str) -> str:
        """从知识库中检索与问题相关的信息。当你需要回答事实性问题或需要参考知识库内容时使用。

        Args:
            query: 要检索的关键词或问题
        """
        try:
            return rag._retrieve(query)
        except RetrieverError as e:
            return f"检索失败: {e.message}"

    return rag_retrieve

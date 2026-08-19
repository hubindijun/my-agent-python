#!/usr/bin/env python
import os

from dotenv import load_dotenv

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()


class MyChat:

    def __init__(self):
        self.llm = ChatOpenAI(
            model=os.getenv("OPENAI_MODEL"),
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE"),
            streaming=True,
        )

        self.prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "你是一个AI助手。请根据用户提供的问题回答。"),
                ("human", "{query}"),
            ]
        )

        self.chain = self.prompt | self.llm | StrOutputParser()

    def chat(self, query: str) -> str:
        return self.chain.invoke({"query": query})

    def rag_chat(self, query: str, context: str) -> str:
        rag_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "请根据下面上下文回答问题。\n\nContext:\n{context}",
                ),
                ("human", "{query}"),
            ]
        )
        chain = rag_prompt | self.llm | StrOutputParser()
        return chain.invoke({"query": query, "context": context})

    def rag_chat_stream(self, query: str, context: str, history: list = None):
        """流式 RAG 对话，支持多轮历史"""
        if history is None:
            history = []

        history_messages = []
        for msg in history:
            if msg["role"] == "user":
                history_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                history_messages.append(AIMessage(content=msg["content"]))

        rag_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个专业的AI助手，请根据提供的上下文回答用户问题。"
                    "如果上下文中没有相关信息，请基于你的知识礼貌回答。\n\n"
                    "Context:\n{context}",
                ),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{query}"),
            ]
        )

        chain = rag_prompt | self.llm | StrOutputParser()
        return chain.stream({"query": query, "context": context, "history": history_messages})

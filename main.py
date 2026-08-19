from my_rag import MyRag


rag = MyRag()
print("RAG初始化完成")

answer = rag.query(
    "猫和狗有什么区别？"
)


print(answer)
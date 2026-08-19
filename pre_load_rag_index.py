from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


class RagIndexer:

    def __init__(
        self,
        model_name="BAAI/bge-small-zh-v1.5",
        embedding_path="./embeddings/",
        persist_directory="./chroma_db",
        vectorstore = None,
    ):

        self.persist_directory = persist_directory

        self.embeddings = HuggingFaceEmbeddings(
            model_name=model_name,
            cache_folder=embedding_path
        )


    def create_index(
        self,
        documents:list[Document]
    ):

        """
        创建向量索引
        """
 
        self.vectorstore = Chroma.from_documents(
            documents=documents,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
        
        )
        
        print(
            f"向量库创建完成，数量:{len(documents)}"
        )

    def similarity_search(self, query: str, k: int = 3):
        """
        相似性搜索（修正拼写）
        """
        if self.vectorstore is None:
            # 如果向量库未初始化，从磁盘加载
            self.vectorstore = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
        
        results = self.vectorstore.similarity_search(query, k=k)
        return results
   




if __name__ == "__main__":

    documents = [
        "猫和狗是完全不同的两种动物",
        "猫和狗这两种动物的差异很大",
        "地球上面有很多种动物",
         """目前已有的期货经验rules
        1.不轻易场外入金，触发强平一定要平，未到强平位保证金不足时，就减仓，不可有再扛扛的侥幸心理，更不能报复性加仓，加仓只适用于未强平前，
        2.也不要轻易反手操作，特别亏损中，反手适合抵达目标位后，平仓后才可，谨慎做日内双边
        3.建仓要具有判断上的确定性，尽量在端点位置附近才建仓，中间位置宁可不做，也不要想着偷鸡短线，除非有较为明确，且振幅较小的止损位（目前止损位尽量设置在涨跌幅5%以内，否则尽量不要建仓，不要用不切实际的止损位，来说服自己去建仓，控制风险）
        4.同一时期尽量不做2个品种，专注一种做好了就对了，永远不同时做2个品种以上
        5.下单前必须想好止损位和目标位，下单后立刻设置止损条件单，同时设置预警位（尽量只设置止盈位的预警，止损位预警很可能导致再熬一熬的情况冒出来，止损单就是为了兼顾反弹回血的机会，与不断巨亏的风险，不宜反复修改）

        6.技巧，降低风险，提高利润空间（非常重要）：
        上涨，下跌过程中，如果是反向建仓，利用条件单设置，有反向趋势才触发建仓！  用少数盈利空间，规避大风险
        无论什么趋势中，建仓都使用条件单，(多单就>=现价成交 | 空单 就<= 限价成交，几个点位即可（0.1%-0.5%））止盈过程中，也可以用止损条件单触发（0.5%-1%的涨跌幅)！只有止损单设置现价不乱改
        7.总结6，建仓用云条件单，止盈用限价止损单，止损用限价止损单

        8. 不做顺势的条件单建仓，否则很容易出现趋势买入，但是反弹亏的情况；而反向的条件单，稍微间隔点距离，至少说明有反弹趋势了！（2026-5-7 已经2把焦煤1283位置低位做空，导致空单成本极高，顺势就算设置靠近的位置，大概率会成交，但是没法保证是否刚把你成交了，过会儿就反弹，除非做超短线，成交后立刻用止损单锁住利润！）
        顺势条件单仅限于投机，甚至不需要条件单
        结论8. 条件单建仓法适合涨时看跌，跌势看涨的情况；偷鸡抢筹的情况，立刻下单，并且盈利后止损单来锁住利润！
        9.如果当天触发止损，千万不要想着继续建仓， 因为触发止损代表趋势已经不确定了，未必反弹，心理上也容易报复性乱来，导致亏损加剧！ （2026-5-12 焦煤空单操作出错，锁赢单成交，之后1286就开始建立多单，最终击穿1282,1279,1260,1252，1242的支撑位，期间反复建仓，被平仓，坐高成本，完全没有规避超跌风险）



        对于各品种近期看法：
        燃油期货的交易，关注布伦特油价涨跌幅，白银反向关注
        玻璃除非反内卷，否则做空比做多风险小，纯碱也是如此
        碳酸锂目前19w高点，但是长期依然未知，波动过大，起步价太高，尽量不接触
        焦煤目前看不清，以震荡行情做，前期一路下跌，切换主连后依然高位，以做空为优先，同时控制好止损位，极端1330
        """
    ]

    docs = [Document(page_content=text) for text in documents]
   
    # 文本分割器（添加中文分隔符）
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,
        chunk_overlap=20,
        separators=["\n\n", "\n", "。", "，", " ", ""]
    )
    
    # 分割文档
    split_docs = text_splitter.split_documents(docs)
    print(f"分割后的文档块数量: {len(split_docs)}")
    
    # 创建索引
    indexer = RagIndexer()
    indexer.create_index(split_docs)
    
    # 相似性搜索（修正拼写）
    results = indexer.similarity_search("说说我的投资策略")
    
    # 打印结果
    print("\n=== 搜索结果 ===")
    for i, doc in enumerate(results):
        print(f"\n结果 {i+1}:")
        print(f"内容: {doc.page_content[:300]}...")  # 显示前300字符
        if doc.metadata:
            print(f"元数据: {doc.metadata}")
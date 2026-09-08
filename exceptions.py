"""
自定义异常体系。

RAGBaseException 为根类，所有子类包含 code / message / status_code，
可直接通过 to_dict() 序列化为 API 错误响应。
"""


class RAGBaseException(Exception):
    code = "INTERNAL_ERROR"
    message = "服务内部错误"
    status_code = 500

    def __init__(self, message=None, detail=None):
        if message:
            self.message = message
        self.detail = detail
        super().__init__(self.message)

    def to_dict(self):
        result = {"code": self.code, "message": self.message}
        if self.detail is not None:
            result["detail"] = self.detail
        return result


class LLMError(RAGBaseException):
    code = "LLM_ERROR"
    message = "LLM 服务异常"
    status_code = 502


class LLMAuthError(LLMError):
    code = "LLM_AUTH_ERROR"
    message = "LLM 鉴权失败"
    status_code = 502


class LLMRateLimitError(LLMError):
    code = "LLM_RATE_LIMIT"
    message = "LLM 调用频率超限，请稍后再试"
    status_code = 503


class LLMServerError(LLMError):
    code = "LLM_SERVER_ERROR"
    message = "LLM 服务端错误"
    status_code = 502


class LLMTimeoutError(LLMError):
    code = "LLM_TIMEOUT"
    message = "LLM 调用超时"
    status_code = 504


class LLMConnectionError(LLMError):
    code = "LLM_CONNECTION_ERROR"
    message = "LLM 服务连接失败"
    status_code = 502


class RetrieverError(RAGBaseException):
    code = "RETRIEVER_ERROR"
    message = "检索服务异常"
    status_code = 500


class VectorStoreInitError(RetrieverError):
    code = "VECTOR_STORE_INIT_ERROR"
    message = "向量数据库初始化失败"
    status_code = 500


class EmbeddingModelError(RetrieverError):
    code = "EMBEDDING_MODEL_ERROR"
    message = "Embedding 模型加载失败"
    status_code = 500


class ValidationError(RAGBaseException):
    code = "VALIDATION_ERROR"
    message = "参数校验失败"
    status_code = 400


class SessionError(RAGBaseException):
    code = "SESSION_ERROR"
    message = "会话异常"
    status_code = 400


class AgentError(RAGBaseException):
    code = "AGENT_ERROR"
    message = "Agent 执行异常"
    status_code = 500

from langchain.embeddings import GPT4AllEmbeddings
from langchain.vectorstores import Chroma
from langchain import PromptTemplate
from langchain_text_splitters import (
    Language,
    RecursiveCharacterTextSplitter,
)
from langchain_core.callbacks.manager import CallbackManagerForRetrieverRun
from langchain.chains import RetrievalQA
from langchain.llms import Ollama
from langchain.schema import HumanMessage, SystemMessage
import os
from langchain_core.vectorstores import BaseRetriever, VectorStoreRetriever
from typing import List
import re
import questllama.core.utils.file_utils as U
import questllama.core.utils.log_utils as L
from rag import CRITIC
from shared import BaseChatProvider, config as C
from shared.messages import QuestllamaMessage
from langchain_core.documents import Document
from questllama.extensions.rag import CustomRetriever
import questllama.core.utils.file_utils as U


class QuestllamaClientProvider(BaseChatProvider):
    """A client provider for Voyager. This class allows you to get a ChatOpenAI client."""

    base_retriever = None
    logger_callback_added = False

    def __init__(self, model_name="gpt-4", temperature=0.0, request_timeout=240):
        super().__init__(
            model_name=model_name,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self.logger = L.QuestLlamaLogger("OllamaAPI")

        self.client = self._get_client(model_name, temperature, request_timeout)

        if QLCP.base_retriever is None:
            QLCP.base_retriever = self.get_retriever(C.SKILL_PATH, C.K, C.SEARCH_TYPE)

    def generate(self, messages, query_type):
        """Generate messages using the LLM. As backend it defaults to Ollama."""
        assert len(messages) <= 2
        assert isinstance(messages[0], SystemMessage)
        assert isinstance(messages[1], HumanMessage)

        retriever = CustomRetriever(
            base_retriever=QLCP.base_retriever, query_type=query_type
        )

        QA_CHAIN_PROMPT = PromptTemplate(
            input_variables=["context", "question"],
            template=messages[0].content,  # system prompt
        )

        qa_chain = RetrievalQA.from_chain_type(
            self.client,
            retriever=retriever,
            chain_type_kwargs={"prompt": QA_CHAIN_PROMPT},
            return_source_documents=True,
        )

        self.result = qa_chain(
            {"query": messages[1].content}, callbacks=[L.LoggerCallbackHandler()]
        )  # user prompt

        return QuestllamaMessage(self.result)

    def _get_client(self, model_name="gpt-4", temperature=0.0, request_timeout=120):
        """
        Returns a new instance of the Ollama client with the provided parameters.
        The handle is used to redirect output to stdout during the output generation.
        """

        return Ollama(
            temperature=temperature, model=model_name, timeout=request_timeout
        )

    def get_retriever(self, lib_path="skill_library", k=10, search_type="similarity"):
        """
        Reads JavaScript files from the skill library stored in a vector store.
        The vector store will be used for information retrieval with the LLM.

        Returns:
            tuple: A tuple containing the vectorstore and the final retriever.
        """
        files = U.read_skill_library(lib_path)
        self.logger.log("info", f"Skill Library. Read {len(files)} javascript files.")

        # FIXME is chunk_size at optimal value?
        js_splitter = RecursiveCharacterTextSplitter.from_language(
            language=Language.JS, chunk_size=60, chunk_overlap=0
        )

        embedding_function = GPT4AllEmbeddings()
        # Check if the persistence directory exists
        if os.path.exists(C.DB_DIR):
            # Load Chroma from the existing directory
            vectorstore = Chroma(
                persist_directory=C.DB_DIR, embedding_function=embedding_function
            )
        else:
            js_docs = js_splitter.create_documents([doc[1] for doc in files])

            # Load Chroma from documents and persist to disk if the directory does not exist
            vectorstore = Chroma.from_documents(
                documents=js_docs,
                embedding=embedding_function,
                persist_directory=C.DB_DIR,
            )

        base_retriever = vectorstore.as_retriever(
            search_kwargs={"k": k}, search_type=search_type
        )

        return base_retriever


QLCP = QuestllamaClientProvider


if __name__ == "__main__":
    import os
    CURRENT = 'critic'

    os.environ["OPENAI_API_KEY"] = "sk-..."
    template = U.debug_load_prompt(CURRENT + "/system.txt")
    user = U.debug_load_prompt(CURRENT + "/user.txt")
    chat = QuestllamaClientProvider()
    msg = chat.generate(
        [
            SystemMessage(content=template),
            HumanMessage(content=user),
        ],
        CURRENT
    )
    print("Answer: ", msg.answer)

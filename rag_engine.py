import os, tempfile
import pinecone
import uuid

from pathlib import Path
from langchain.chains import RetrievalQA, ConversationalRetrievalChain
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from langchain import OpenAI
from langchain.llms.openai import OpenAIChat
from langchain.document_loaders import DirectoryLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma, Pinecone
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain.memory.chat_message_histories import StreamlitChatMessageHistory

import streamlit as st

st.set_page_config(page_title="RAG")
st.title("Retrieval Augmented Generation Engine")

TMP_DIR = Path('Temp_Files')  # This will create Temp_Files in the current directory of the app

TMP_DIR.mkdir(parents=True, exist_ok=True)

test_file_path = TMP_DIR / "test_file.pdf"

with open(test_file_path, "wb") as f:
    f.write(b"Test content")

st.write("Test file created successfully at:", test_file_path)

#TMP_DIR = Path(__file__).resolve().parent.joinpath('data', 'tmp')
LOCAL_VECTOR_STORE_DIR = Path(__file__).resolve().parent.joinpath('data', 'vector_store')


def load_documents():
    loader = DirectoryLoader(TMP_DIR.as_posix(), glob='**/*.pdf')
    documents = loader.load()
    return documents

def split_documents(documents):
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_documents(documents)
    return texts

def embeddings_on_local_vectordb(texts):
    vectordb = Chroma.from_documents(texts, embedding=OpenAIEmbeddings(openai_api_key=st.session_state.openai_api_key),
                                     persist_directory=LOCAL_VECTOR_STORE_DIR.as_posix())
    vectordb.persist()
    retriever = vectordb.as_retriever(search_kwargs={'k': 7})
    return retriever

def embeddings_on_pinecone(texts):
    pinecone.init(api_key=st.session_state.pinecone_api_key, environment=st.session_state.pinecone_env)
    embeddings = OpenAIEmbeddings(openai_api_key=st.session_state.openai_api_key)
    vectordb = Pinecone.from_documents(texts, embeddings, index_name=st.session_state.pinecone_index)
    retriever = vectordb.as_retriever()
    return retriever

def query_llm(retriever, query):
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=OpenAIChat(openai_api_key=st.session_state.openai_api_key),
        retriever=retriever,
        return_source_documents=True,
    )
    result = qa_chain({'question': query, 'chat_history': st.session_state.messages})
    result = result['answer']
    st.session_state.messages.append((query, result))
    return result

def input_fields():
    #
    with st.sidebar:
        #
        if "openai_api_key" in st.secrets:
            st.session_state.openai_api_key = st.secrets.openai_api_key
        else:
            st.session_state.openai_api_key = st.text_input("OpenAI API key", type="password")
        #
        if "pinecone_api_key" in st.secrets:
            st.session_state.pinecone_api_key = st.secrets.pinecone_api_key
        else: 
            st.session_state.pinecone_api_key = st.text_input("Pinecone API key", type="password")
        #
        if "pinecone_env" in st.secrets:
            st.session_state.pinecone_env = st.secrets.pinecone_env
        else:
            st.session_state.pinecone_env = st.text_input("Pinecone environment")
        #
        if "pinecone_index" in st.secrets:
            st.session_state.pinecone_index = st.secrets.pinecone_index
        else:
            st.session_state.pinecone_index = st.text_input("Pinecone index name")
    #
    st.session_state.pinecone_db = st.toggle('Use Pinecone Vector DB')
    #
    st.session_state.source_docs = st.file_uploader(label="Upload Documents", type="pdf", accept_multiple_files=True)
    #

def process_documents():
    if not st.session_state.source_docs:
        st.warning("Please upload the documents.")
        return

    try:
        texts = [] # Initialize an empty list to hold all texts from all documents
        for source_doc in st.session_state.source_docs:
            # Generate a unique file path
            temp_file_path = TMP_DIR / f"{uuid.uuid4()}.pdf"

            # Write the content to the file
            with open(temp_file_path, "wb") as f:
                f.write(source_doc.getbuffer())

            # Load, process, and clean up as before
            # Ensure that these functions use 'temp_file_path' correctly

        # If using local vectordb
        if not st.session_state.pinecone_db:
            st.session_state.retriever = embeddings_on_local_vectordb(texts)
        else:
            st.session_state.retriever = embeddings_on_pinecone(texts)
    except Exception as e:
        st.error(f"An error occurred: {e}")

def boot():
    #
    input_fields()
    #
    st.button("Submit Documents", on_click=process_documents)
    #
    if "messages" not in st.session_state:
        st.session_state.messages = []    
    #
    for message in st.session_state.messages:
        st.chat_message('human').write(message[0])
        st.chat_message('ai').write(message[1])    
    #
    if query := st.chat_input():
        if 'retriever' not in st.session_state:
            st.error("Retriever is not initialized. Please submit documents first.")
        else:
            st.chat_message("human").write(query)
            response = query_llm(st.session_state.retriever, query)
            st.chat_message("ai").write(response)

if __name__ == '__main__':
    #
    boot()
    

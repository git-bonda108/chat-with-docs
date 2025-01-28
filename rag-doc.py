import os
import tempfile
from openai import OpenAI
import streamlit as st
from dotenv import load_dotenv
from langchain.chains import ConversationalRetrievalChain
from langchain.document_loaders import PyPDFLoader, TextLoader, UnstructuredWordDocumentLoader
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.memory import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI

# Load environment variables
load_dotenv()

# Initialize OpenAI API
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("API key not found. Please set OPENAI_API_KEY in your .env file.")

openai_client = OpenAI(api_key=api_key)


# Helper Functions
def save_and_load_files(uploaded_files):
    """Saves uploaded files temporarily and extracts text."""
    documents = []
    for uploaded_file in uploaded_files:
        file_extension = os.path.splitext(uploaded_file.name)[-1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(uploaded_file.read())
            temp_file_path = temp_file.name

        if file_extension == ".pdf":
            loader = PyPDFLoader(temp_file_path)
        elif file_extension == ".txt":
            loader = TextLoader(temp_file_path)
        elif file_extension in [".doc", ".docx"]:
            loader = UnstructuredWordDocumentLoader(temp_file_path)
        else:
            st.error(f"Unsupported file format: {file_extension}")
            continue

        documents.extend(loader.load())
        os.unlink(temp_file_path)  # Clean up temp files
    return documents


def create_faiss_vectorstore(documents):
    """Creates a FAISS vectorstore from the documents."""
    embeddings = OpenAIEmbeddings()
    vectorstore = FAISS.from_documents(documents, embeddings)
    return vectorstore


def build_conversational_chain(vectorstore):
    """Builds a conversational chain with FAISS vectorstore and memory."""
    memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
    conversational_chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(model="gpt-4", temperature=0, openai_api_key=os.getenv("OPENAI_API_KEY")),
        retriever=vectorstore.as_retriever(),
        memory=memory
    )
    return conversational_chain


def summarize_text(vectorstore):
    """Generates a summary of the text in the vectorstore."""
    # Retrieve all documents directly from the vectorstore
    all_documents = vectorstore.docstore._dict.values()  # Access the raw documents
    text = "\n".join([doc.page_content for doc in all_documents])

    prompt = (
        "You are an assistant tasked with summarizing content across multiple files. The summary must be structured and professional."
        "Organize the summary into key points:\n"
        "- Highlights:\n- Key Takeaways:\n- Actionable Insights:\n"
        f"Here's the text to summarize: {text}"
    )

    completion = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "developer", "content": "You are a helpful summarization assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    summary = completion.choices[0].message.content
    return summary


# Streamlit App
st.title("Conversational Chatbot for File Interaction")
st.write("Upload files (PDF, DOC, TXT) to interact and get summaries.")

uploaded_files = st.file_uploader("Upload Files", accept_multiple_files=True, type=["pdf", "doc", "docx", "txt"])

if uploaded_files:
    st.write("### Step 1: Loading Files")
    with st.spinner("Loading and processing files..."):
        documents = save_and_load_files(uploaded_files)

    if not documents:
        st.error("No valid documents loaded.")
    else:
        st.success("Files loaded successfully!")

        st.write("### Step 2: Creating Vectorstore")
        with st.spinner("Building FAISS vectorstore..."):
            vectorstore = create_faiss_vectorstore(documents)
        st.success("Vectorstore created successfully!")

        st.write("### Step 3: Generating Summary")
        with st.spinner("Summarizing content..."):
            summary = summarize_text(vectorstore)
        st.success("Summary generated successfully!")
        st.write("### Summary:")
        st.write(summary)

        st.write("### Step 4: Conversational Chat")
        st.write("Ask questions based on the uploaded files.")
        conversational_chain = build_conversational_chain(vectorstore)

        user_question = st.text_input("Your Question:")
        if st.button("Ask"):
            with st.spinner("Generating response..."):
                response = conversational_chain.run(user_question)
            st.write("### Response:")
            st.write(response)

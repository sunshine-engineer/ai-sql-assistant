
import re
import time
import traceback

import streamlit as st 
from pathlib import Path 
from langchain_community.utilities import SQLDatabase
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler 
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from sqlalchemy import create_engine
import sqlite3
from langchain_groq import ChatGroq


BLOCKED_PATTERNS = [
    r"\bdrop\b",
    r"\bdelete\b",
    r"\btruncate\b",
    r"\balter\b",
    r"\binsert\b",
    r"\bupdate\b",
    r"\bcreate\b",
    r"\breplace\b",
    r"\bgrant\b",
    r"\brevoke\b",
    r"\bexecute\b",
    r"\bexec\b",
    r"\bshutdown\b",
]


def validate_user_query(query: str):
    """
    Validate the user's natural language request before sending it to the LLM.
    Returns (is_safe, message).
    """
    q = query.lower()

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, q):
            return (
                False,
                "❌ This application only allows read-only database operations."
            )

    return True, ""


st.set_page_config(
    page_title="AI SQL Assistant",
    page_icon="🤖",
    layout="wide",
)
st.title("🤖 AI SQL Assistant")

st.caption(
    "Ask questions in natural language and let an AI agent query your SQL database."
)

st.sidebar.markdown("## 🤖 AI SQL Assistant")
st.sidebar.info(
    """
**Portfolio Project**

💬 Natural Language → SQL

🛠 LangChain SQL Agent

🧠 Groq Llama 3.3 70B

🗄 SQLite • MySQL • PostgreSQL
"""
)


LOCALDB="USE_LOCALDB"
MYSQL="USE_MYSQL"
POSTGRES = "USE_POSTGRES"


radio_opt=["Use SQLLite 3 Database Students.db",
           "Connect to you SQL Database",
           "PostgreSQL Database"
           ]

selected_opt=st.sidebar.radio(label="Choose the DB which you want to chat",
                           options=radio_opt)

if radio_opt.index(selected_opt)==1:
    db_uri=MYSQL
    mysql_host=st.sidebar.text_input("Provide My SQL Host")
    mysql_user=st.sidebar.text_input("MySQL User")
    mysql_password=st.sidebar.text_input("MySQL password",type="password" )
    mysql_db=st.sidebar.text_input("MySQL Database")

elif radio_opt.index(selected_opt)==2:
    db_uri = POSTGRES 
    
    postgres_host = st.sidebar.text_input("Host")
    postgres_port = st.sidebar.text_input("Port", value="5432")
    postgres_user = st.sidebar.text_input("Username")
    postgres_password = st.sidebar.text_input("Password", type="password")
    postgres_db = st.sidebar.text_input("Database")


else:
    db_uri=LOCALDB

groq_api_key=st.sidebar.text_input(label="Groq API Key", type="password")


if not db_uri:
    st.info("Please enter database uri")

if not groq_api_key:
    st.info("Please add the groq api key")
    st.stop()


MODEL_NAME = "qwen/qwen3.6-27b"

## LLM Model 
llm = ChatGroq(
        api_key=groq_api_key,
        # model="llama-3.3-70b-versatile", ## openai/gpt-oss-120b
        # model="openai/gpt-oss-20b", ## qwen/qwen3.6-27b
        model=MODEL_NAME,
        temperature=0,
        streaming=True,
    )

## Configure

@st.cache_resource(ttl="2h")
def configure_db(
    db_uri,
    mysql_host=None,
    mysql_user=None,
    mysql_password=None,
    mysql_db=None,
    postgres_host=None,
    postgres_port=None,
    postgres_user=None,
    postgres_password=None,
    postgres_db=None,
):
    if db_uri==LOCALDB:
         db_file_path = Path(__file__).parent.resolve() / "student.db"
         st.sidebar.caption(f"Database: {db_file_path.name}")
         creator = lambda: sqlite3.connect(f"file:{db_file_path}?mode=ro", uri=True)
         return SQLDatabase(create_engine("sqlite:///", creator=creator))
    elif db_uri==MYSQL:
        if not (mysql_host and mysql_user and mysql_password and mysql_db):
            st.error("Please provide all MySQL connection details.")
            st.stop()
        return SQLDatabase(create_engine(f"mysql+mysqlconnector://{mysql_user}:{mysql_password}@{mysql_host}/{mysql_db}"))   
    
    elif db_uri == POSTGRES:
        if not (
            postgres_host
            and postgres_user
            and postgres_password
            and postgres_db
        ):
            st.error("Please provide PostgreSQL connection details.")
            st.stop()
        
        engine = create_engine(
            f"postgresql+psycopg://"
            f"{postgres_user}:{postgres_password}"
            f"@{postgres_host}:{postgres_port}"
            f"/{postgres_db}"
        )
        
        return SQLDatabase(engine)

if db_uri==MYSQL:
    db=configure_db(db_uri,mysql_host,mysql_user,mysql_password,mysql_db)

elif db_uri==POSTGRES:    
        db = configure_db(
        db_uri,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
        postgres_db=postgres_db,
        )

else:
    db=configure_db(db_uri)
    
    
## Toolkit 

def create_agent(_db, _llm):
    return create_sql_agent(
        llm=_llm,
        db=_db,
        agent_type="tool-calling",
        verbose=True,
        prefix="""
        You are a professional SQL assistant.
        
        Rules:
        - Only generate READ ONLY SQL.
        - Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE, REPLACE, GRANT or REVOKE.
        - Never modify database data.
        - Never modify database schema.
        - Prefer SELECT queries.
        - Use LIMIT where appropriate.
        - If the user requests any write operation, politely refuse.
        """
    )


agent = create_agent(db, llm)

with st.sidebar.expander("📊 Database Information", expanded=True):

    st.write(f"**Database Type:** {selected_opt}")

    try:
        table_names = db.get_usable_table_names()

        st.write(f"**Available Tables:** {len(table_names)}")

        st.caption(", ".join(table_names[:10]))

        if len(table_names) > 10:
            st.caption("...")

    except Exception:
        st.warning("Unable to retrieve schema information.")

if "messages" not in st.session_state or st.sidebar.button("Clear message history"):
    st.session_state["messages"] = [{"role": "assistant", "content": "How can I help you?"}]

for msg in st.session_state.messages:
    avatar = "🤖" if msg["role"] == "assistant" else "👤"
    with st.chat_message(msg["role"], avatar=avatar):
        st.write(msg["content"])

user_query=st.chat_input(placeholder="Ask anything from the database")

if user_query:
    # 1. Always display/store the user's message
    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_query,
        }
    )

    with st.chat_message("user", avatar="👤"):
        st.write(user_query)

    # 2. Validate it
    is_safe, message = validate_user_query(user_query)
    if not is_safe:
        st.error(message)
    
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": message,
            }
        )
    
        st.stop()

    st.session_state.messages.append({"role": "user",
                                      "content": user_query})
    
    with st.chat_message("user", avatar="👤"):
        st.write(user_query)

    with st.chat_message("assistant", avatar="🤖"):
        callback_container = st.expander(
                    "🛠 Agent Reasoning",
                    expanded=False,
                )
        # streamlit_callback=StreamlitCallbackHandler(callback_container)
        
        with st.spinner("🤖 Analyzing your question and querying the database..."):
            elapsed = 0
            try:
                start=time.perf_counter()
                
                response = agent.invoke(
                    {
                        "input": user_query
                    },
#                     config={"callbacks": [streamlit_callback]},
                )
                
                answer = response["output"]
                elapsed = time.perf_counter() - start
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )
                st.write(answer)
                
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Response Time", f"{elapsed:.2f}s")
                
                with col2:
                    st.metric("Model", MODEL_NAME)
                
                with col3:
                    st.metric("Database", selected_opt.replace("Use ", ""))       
                            
            except Exception as e:

                traceback.print_exc()
                st.exception(e)
            
                if hasattr(e, "body"):
                    st.write(e.body)
            
                answer = str(e)
            
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": answer,
                    }
                )
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
st.set_page_config(page_title="LibraryGenie | School AI Library Agent", page_icon="🧞", layout="wide")

DB_PATH = Path(__file__).with_name("library.db")
MODEL_NAME = "openai/gpt-oss-120b"
MAX_RESULT_ROWS = 50

# Custom CSS for styling
st.markdown("""
<style>
.block-container {max-width: 1250px; padding-top: 2rem;}
[data-testid="stMetric"] {background: rgba(91,122,255,0.075); border: 1px solid rgba(128,140,176,0.18); border-radius: 14px; padding: 14px;}
[data-testid="stChatMessage"] {border: 1px solid rgba(128,140,176,0.16); border-radius: 14px;}
</style>
""", unsafe_allow_html=True)

def get_connection():
    uri = f"{DB_PATH.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection

def get_schema():
    return {"books": ["book_id (INTEGER)", "title (TEXT)", "author (TEXT)", "category (TEXT)", "available_copies (INTEGER)", "times_borrowed (INTEGER)"]}

def create_sql_plan(client, question, schema_text, previous_sql="", error_text=""):
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "library_sql_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string"},
                    "assumption": {"type": "string"},
                },
                "required": ["sql", "assumption"],
                "additionalProperties": False,
            },
        },
    }
    system_prompt = f"""
You are LibraryGenie, an AI assistant for a school library.
Translate the user question (which could be in English or Roman Urdu) into ONE SQLite SELECT statement using only this schema:
{schema_text}

Rules:
- Return a single read-only SELECT or WITH...SELECT statement. Never produce write operations (INSERT, UPDATE, DELETE).
- Match Roman Urdu terms correctly to category names (e.g., 'Science category mein' means category = 'Science').
- For 'most borrowed books', sort by times_borrowed DESC.
- For 'zero available copies', filter where available_copies = 0.
- Never pretend to have run a query. Python will execute your SQL separately.
"""
    correction = f"Previous SQL: {previous_sql}\nDatabase error: {error_text}\nFix the SQL using the schema." if error_text else ""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question + "\n" + correction},
        ],
        temperature=0,
        response_format=response_format,
    )
    return json.loads(response.choices[0].message.content or "{}")

def execute_read_only_sql(sql):
    statement = sql.strip()
    if not statement or not statement.lower().lstrip().startswith(("select ", "with ")):
        raise ValueError("Only read-only SELECT statements are allowed.")

    def only_reads(action, arg1, arg2, database, source):
        if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ):
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in {
            "count", "sum", "avg", "min", "max", "total"
        }:
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    connection = get_connection()
    connection.set_authorizer(only_reads)
    try:
        cursor = connection.execute(statement)
        rows = cursor.fetchmany(MAX_RESULT_ROWS + 1)
        column_names = [column[0] for column in cursor.description]
        limited = len(rows) > MAX_RESULT_ROWS
        dataframe = pd.DataFrame([tuple(row) for row in rows[:MAX_RESULT_ROWS]], columns=column_names)
        return dataframe, limited
    except sqlite3.Error as error:
        raise ValueError(f"Database rejected the query: {error}")
    finally:
        connection.close()

def explain_results(client, question, sql, dataframe):
    preview = dataframe.head(15).to_csv(index=False)
    prompt = f"""
You are LibraryGenie, explaining real SQL outcomes to students in simple English.
Provide a clear answer based on this data. Do not make up facts.
User question: {question}
Executed SQL: {sql}
Result Data (CSV):
{preview}
Give a concise answer of 2 to 4 sentences.
"""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content or "No explanation generated."

# UI Layout
st.title("🧞 LibraryGenie")
st.caption("AI School Library Agent | Ask questions in English or Roman Urdu")

if not DB_PATH.exists():
    st.error("library.db was not found. Please run create_library_db.py first.")
    st.stop()

with st.sidebar:
    st.header("Control Center")
    api_key = st.text_input("Groq API Key", value=os.getenv("GROQ_API_KEY", ""), type="password")
    st.success("Database Security: Read-Only (SELECT Only)")
    if st.button("Clear History", use_container_width=True):
        st.session_state.lib_history = []
        st.session_state.active_q = ""
        st.rerun()

# Overview Statistics
with closing(get_connection()) as conn:
    stats = pd.read_sql_query(
        "SELECT COUNT(*) as total_books, SUM(available_copies) as total_avail, SUM(times_borrowed) as total_borrows FROM books", conn
    ).iloc[0]

c1, c2, c3 = st.columns(3)
c1.metric("Total Books Titles", int(stats["total_books"]), border=True)
c2.metric("Available Copies on Shelves", int(stats["total_avail"]), border=True)
c3.metric("Total Times Borrowed", int(stats["total_borrows"]), border=True)

tab_ask, tab_chart = st.tabs(["🧠 Ask LibraryGenie", "📊 Borrowing Analytics (Bonus)"])

if "lib_history" not in st.session_state:
    st.session_state.lib_history = []
if "active_q" not in st.session_state:
    st.session_state.active_q = ""

with tab_ask:
    st.subheader("Quick Test Questions")
    q1, q2, q3, q4, q5 = st.columns(5)
    if q1.button("Q1: Total Books?", use_container_width=True): st.session_state.active_q = "How many books are in the library?"
    if q2.button("Q2: Top 5 Borrowed?", use_container_width=True): st.session_state.active_q = "Show the 5 most borrowed books."
    if q3.button("Q3: Science Books Urdu?", use_container_width=True): st.session_state.active_q = "Science category mein kitni books hain?"
    if q4.button("Q4: Out of Stock?", use_container_width=True): st.session_state.active_q = "Which books have zero available copies?"
    if q5.button("Q5: Top Category?", use_container_width=True): st.session_state.active_q = "Which category has the highest total borrowings?"

    # Display Chat Logs
    for msg in st.session_state.lib_history:
        with st.chat_message("user"): st.markdown(msg["question"])
        with st.chat_message("assistant"):
            st.markdown(msg["answer"])
            with st.expander("Show Evidence / SQL Context"):
                st.caption("**Source Label:** books table")
                st.code(msg["sql"], language="sql")
                st.dataframe(pd.DataFrame(msg["rows"]), hide_index=True)

    text_input = st.chat_input("Type your library question here...")
    final_query = st.session_state.active_q or text_input
    st.session_state.active_q = ""

    if final_query:
        if not api_key:
            st.warning("Please provide your Groq API Key in the sidebar.")
        else:
            try:
                client = Groq(api_key=api_key)
                schema_info = "books: book_id, title, author, category, available_copies, times_borrowed"
                
                with st.status("LibraryGenie is looking up the database...", expanded=True) as status:
                    plan = create_sql_plan(client, final_query, schema_info)
                    sql_cmd = plan.get("sql", "").strip()
                    
                    if not sql_cmd:
                        raise ValueError("The query generated was invalid.")
                        
                    df, limited = execute_read_only_sql(sql_cmd)
                    explanation = explain_results(client, final_query, sql_cmd, df)
                    status.update(label="Lookup Completed!", state="complete", expanded=False)

                with st.chat_message("user"): st.markdown(final_query)
                with st.chat_message("assistant"):
                    st.markdown(explanation)
                    st.caption("**Source Label:** books table")
                    st.dataframe(df, hide_index=True)
                    with st.expander("Generated SQL Query"):
                        st.code(sql_cmd, language="sql")

                st.session_state.lib_history.append({
                    "question": final_query,
                    "answer": explanation,
                    "sql": sql_cmd,
                    "rows": df.to_dict(orient="records")
                })
            except Exception as e:
                st.error(f"Error handling query: {e}")

with tab_chart:
    st.subheader("Total Borrowings by Category")
    with closing(get_connection()) as conn:
        chart_df = pd.read_sql_query(
            "SELECT category, SUM(times_borrowed) as total_borrowed FROM books GROUP BY category ORDER BY total_borrowed DESC", conn
        )
    st.bar_chart(chart_df, x="category", y="total_borrowed")

"""
demo_app.py
"""
import streamlit as st
from openai import OpenAI
from utils import (
    EventHandler,
    moderation_endpoint,
    is_nsfw,
    # is_not_question,
    render_custom_css
    )

# Initialise the OpenAI client, and retrieve the assistant
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
assistant = client.beta.assistants.retrieve(st.secrets["ASSISTANT_ID"])

st.set_page_config(page_title="DAVE",
                   page_icon="🕵️")

# Apply custom CSS
render_custom_css()

# Create a new thread
if "thread_id" not in st.session_state:
    thread = client.beta.threads.create()
    st.session_state.thread_id = thread.id
    print(st.session_state.thread_id)

# We should store this thread_id, and run a separate script to delete all threads every hour

# Initialise session state variables
if "file_uploaded" not in st.session_state:
    st.session_state.file_uploaded = False

if "assistant_text" not in st.session_state:
    st.session_state.assistant_text = [""]

if "code_input" not in st.session_state:
    st.session_state.code_input = []

if "code_output" not in st.session_state:
    st.session_state.code_output = []

if "disabled" not in st.session_state:
    st.session_state.disabled = False

# UI
st.subheader("DAVE: Data Analysis & Visualisation Engine")
st.markdown("This demo uses a data.gov.sg dataset on HDB resale prices.", help="[Source](https://beta.data.gov.sg/collections/189/datasets/d_ebc5ab87086db484f88045b47411ebc5/view)")
text_box = st.empty()
qn_btn = st.empty()

# Attach the file to the thread
message = client.beta.threads.messages.create(
    thread_id=st.session_state.thread_id,
    role="user",
    content="Here is a dataset. Analyse it",
    file_ids=[st.secrets["FILE_ID"]]
)

question = text_box.text_input("Ask a question", disabled=st.session_state.disabled)
if qn_btn.button("Ask DAVE"):

    text_box.empty()
    qn_btn.empty()

    if moderation_endpoint(question) or is_nsfw(question):
        st.warning("Your question has been flagged. Refresh page to try again.")
        client.beta.threads.delete(st.session_state.thread_id)
        st.stop()

    # if is_not_question(question):
    #     st.warning("Please ask a question. Refresh page to try again.")
    #     client.beta.threads.delete(st.session_state.thread_id)
    #     st.stop()

    if "text_boxes" not in st.session_state:
        st.session_state.text_boxes = []

    message = client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=question
    )

    st.session_state.text_boxes.append(st.empty())
    st.session_state.text_boxes[-1].success(f"**> 🤔 User:** {question}")

    with client.beta.threads.runs.create_and_stream(thread_id=st.session_state.thread_id,
                                                    assistant_id=assistant.id,
                                                    event_handler=EventHandler()
    ) as stream:
        stream.until_done()
        st.toast("DAVE has finished analysing the data", icon="🕵️")

        # Clean-up
        client.beta.threads.delete(st.session_state.thread_id)

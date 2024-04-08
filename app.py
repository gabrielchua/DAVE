"""
app.py
"""
import os

import streamlit as st
from openai import OpenAI
from utils import (
    EventHandler, 
    delete_uploaded_files,
    delete_thread,
    is_nsfw,
    moderation_endpoint,
    render_custom_css,
    update_google_sheet
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

# Initialise session state variables
if "file" not in st.session_state:
    st.session_state.file = None

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
st.subheader("🔮 DAVE: Data Analysis & Visualisation Engine")
file_upload_box = st.empty()
upload_btn = st.empty()
text_box = st.empty()
qn_btn = st.empty()

# File Upload
if not st.session_state["file_uploaded"]:
    st.session_state["files"] = file_upload_box.file_uploader("Please upload your dataset(s).", 
                                                             accept_multiple_files=True,
                                                             type=["csv", "xlsx", "xls"])

    if upload_btn.button("Upload"):

        st.session_state["file_id"] = []

        # Upload the file
        for file in st.session_state["files"]:
            oai_file = client.files.create(
                file=file,
                purpose='assistants'
            )

            # Append the file ID to the list
            st.session_state["file_id"].append(oai_file.id)
            # Update the Google Sheet to faciliate manual deletion
            update_google_sheet("public", "file", oai_file.id)

        st.toast("File uploaded successfully", icon="✨")
        st.session_state["file_uploaded"] = True
        file_upload_box.empty()
        upload_btn.empty()
        st.rerun()

if st.session_state["file_uploaded"]:
    question = text_box.text_area("Ask a question", disabled=st.session_state.disabled)
    if qn_btn.button("Ask DAVE"):

        text_box.empty()
        qn_btn.empty()

        if moderation_endpoint(question) or is_nsfw(question):
            st.warning("Your question has been flagged. Refresh page to try again.")
            delete_uploaded_files()
            st.stop()

        if "text_boxes" not in st.session_state:
            st.session_state.text_boxes = []

        # Create a new thread
        if "thread_id" not in st.session_state:
            thread = client.beta.threads.create()
            st.session_state.thread_id = thread.id
            # Update the Google Sheet to faciliate manual deletion
            update_google_sheet("public", "thread", thread.id)
            print(st.session_state.thread_id)

        # Attach the file(s) to the thread
        message = client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content="Here is a dataset. Analyse it",
            file_ids=[file_id for file_id in st.session_state.file_id]
        )

        # Ask the question
        message = client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=question,
        )

        st.session_state.text_boxes.append(st.empty())
        st.session_state.text_boxes[-1].success(f"**> 🤔 User:** {question}")

        with client.beta.threads.runs.stream(thread_id=st.session_state.thread_id,
                                             assistant_id=assistant.id,
                                             event_handler=EventHandler(),
                                             temperature=0) as stream:
            stream.until_done()
            st.toast("DAVE has finished analysing the data", icon="🕵️")

        # Retrieve the messages by the Assistant from the thread
        thread_messages = client.beta.threads.messages.list(st.session_state.thread_id)
        assistant_messages = []
        for message in thread_messages.data:
            if message.role == "assistant":
                assistant_messages.append(message.id)

        # For each assistant message, retrieve the file(s) created by the Assistant
        assistant_created_file_ids = []
        for message_id in assistant_messages:
            message_files = client.beta.threads.messages.files.list(
                thread_id=st.session_state.thread_id,
                message_id=message_id)
            for file in message_files.data:
                assistant_created_file_ids.append(file.id)
        
        # Download these files
        for file_id in assistant_created_file_ids:
            content = client.files.content(file_id)
            file_name = client.files.retrieve(file_id).filename
            file_name = os.path.basename(file_name)
            st.download_button(label=f"Download `{file_name}`",
                               data=content,
                               file_name=file_name, 
                               use_container_width=True)

        # Clean-up
        # Delete the file(s) uploaded
        delete_uploaded_files()
        
        # Delete the file(s) created by the Assistant
        for file_id in assistant_created_file_ids:
            client.files.delete(file_id)
            print(f"Deleted assistant-created file {file_id}")
            
        # Delete the thread
        delete_thread(st.session_state.thread_id)

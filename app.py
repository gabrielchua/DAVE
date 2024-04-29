"""
app.py
"""
import os

import streamlit as st
from openai import OpenAI
from openai.types.beta.thread_create_params import CodeInterpreterToolParam
from utils import (
    delete_files,
    delete_thread,
    EventHandler,
    initialise_session_state,
    moderation_endpoint,
    render_custom_css,
    render_download_files,
    retrieve_messages_from_thread,
    retrieve_assistant_created_files
    )

# Get secrets
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", st.secrets["OPENAI_API_KEY"])
ASSISTANT_ID = os.environ.get("OPENAI_ASSISTANT_ID", st.secrets["OPENAI_ASSISTANT_ID"])

# Initialise the OpenAI client, and retrieve the assistant
client = OpenAI(api_key=OPENAI_API_KEY)
assistant = client.beta.assistants.retrieve(ASSISTANT_ID)

st.set_page_config(page_title="DAVE",
                   page_icon="🕵️")

# Apply custom CSS
render_custom_css()

# Initialise session state variables
initialise_session_state()

# UI
st.subheader("🔮 DAVE: Data Analysis & Visualisation Engine")
file_upload_box = st.empty()
upload_btn = st.empty()
text_box = st.empty()
qn_btn = st.empty()

# File Upload
if not st.session_state["file_uploaded"]:
    st.session_state["files"] = file_upload_box.file_uploader("Please upload your dataset(s)",
                                                              accept_multiple_files=True,
                                                              type=["csv"])

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
            print(f"Uploaded new file: \t {oai_file.id}")

        st.toast("File(s) uploaded successfully", icon="🚀")
        st.session_state["file_uploaded"] = True
        file_upload_box.empty()
        upload_btn.empty()
        # The re-run is to trigger the next section of the code
        st.rerun()

if st.session_state["file_uploaded"]:
    
    question = text_box.text_area("Ask a question")

    # If the button is clicked
    if qn_btn.button("Ask DAVE"):

        # Clear the UI
        text_box.empty()
        qn_btn.empty()

        # Check if the question is flagged
        if moderation_endpoint(question):
            # if flagged, return a warning message, delete the files and stop the app
            st.warning("Your question has been flagged. Refresh page to try again.")
            delete_files(st.session_state.file_id)
            st.stop()

        # If there is no text boxes in the session state, create an empty list 
        # This list will store the text boxes created by the Assistant
        if "text_boxes" not in st.session_state:
            st.session_state.text_boxes = []

        # Create a new thread if not already created
        if "thread_id" not in st.session_state:
            thread = client.beta.threads.create()
            st.session_state.thread_id = thread.id
            print(f"Created new thread: \t {st.session_state.thread_id}")

        # Update the thread to attach the file(s)
        client.beta.threads.update(
            thread_id=st.session_state.thread_id,
            tool_resources={"code_interpreter": {"file_ids": [file_id for file_id in st.session_state.file_id]}}
            )

        # Ask the question
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role="user",
            content=question,
        )

        # Create a new text box to display the question
        st.session_state.text_boxes.append(st.empty())
        st.session_state.text_boxes[-1].success(f"**> 🤔 User:** {question}")

        # Run the Assistant and the EventHandler handles the stream
        with client.beta.threads.runs.stream(thread_id=st.session_state.thread_id,
                                             assistant_id=assistant.id,
                                             tool_choice={"type": "code_interpreter"},
                                             event_handler=EventHandler(),
                                             temperature=0) as stream:
            stream.until_done()
            st.toast("DAVE has finished analysing the data", icon="🕵️")

        # Prepare the files for download
        with st.spinner("Preparing the files for download..."):
            # Retrieve the messages by the Assistant from the thread
            assistant_messages = retrieve_messages_from_thread(st.session_state.thread_id)
            # For each assistant message, retrieve the file(s) created by the Assistant
            st.session_state.assistant_created_file_ids = retrieve_assistant_created_files(assistant_messages)
            # Download these files
            st.session_state.download_files, st.session_state.download_file_names = render_download_files(st.session_state.assistant_created_file_ids)

        # Clean-up
        # Delete the file(s) uploaded
        delete_files(st.session_state.file_id)
        # Delete the file(s) created by the Assistant
        delete_files(st.session_state.assistant_created_file_ids)
        # Delete the thread
        delete_thread(st.session_state.thread_id)

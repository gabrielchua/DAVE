# DAVE: Data Analysis & Visualisation Engine
[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://dave-demo.streamlit.app/)

This Streamlit application analyses a given dataset with OpenAI's [Assistants API](https://platform.openai.com/docs/assistants/overview) with [Code Interpreter](https://platform.openai.com/docs/assistants/tools/code-interpreter). The Assistant's analysis, including the Python code the assistant will write & execute, will streamed to the app's user interface.

<p align="center">
  <img src="demo/demo1.gif" alt="Demo 1" width="40%" style="border: 3px solid black;"/>
  <img src="demo/demo2.gif" alt="Demo 2" width="40%" style="border: 3px solid black;"/>
</p>

## Quick Start

1. Clone this repository
2. Install the required dependencies by running

```python
pip install -r requirements.txt
```
   
3. Modify `create_assistant.py` as needed, and note down the `ASSISTANT_ID`.
4. Create a `secrets.toml` file located within the `.streamlit/` directory. It should minimally contain these variables: `OPENAI_API_KEY`, `ASSISTANT_ID`
5. Launch the application:

```python
streamlit run demo_app.py
```

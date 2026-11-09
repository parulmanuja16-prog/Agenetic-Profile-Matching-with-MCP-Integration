# MCP Integration Demo

The narrated 5–6 minute walkthrough is
[`demos/mcp_end_to_end_demo.mp4`](../demos/mcp_end_to_end_demo.mp4). Its
editable PowerPoint source is
[`demos/mcp_end_to_end_demo.pptx`](../demos/mcp_end_to_end_demo.pptx).

The video visualizes the implemented workflow; it is not a live screen capture.
The slides cover the two MCP server processes, filesystem resources and tools,
Streamlit batch/watch controls, the matching flow, optional SQLite question-bank
reads, and conversation follow-ups.

## Run the application alongside the video

From the project root, activate the Python environment and start each server
in its own PowerShell window:

```powershell
.\.venv\Scripts\python.exe filesystem_mcp_server.py
```

```powershell
.\.venv\Scripts\python.exe interview_mcp_server.py
```

In another window, run Streamlit:

```powershell
.\.venv\Scripts\python.exe -m streamlit run ui\streamlit_app.py
```

In the app, try a search such as `Find candidates with Python and 3+ years
experience`, use the sidebar's batch or watch actions, enable **Use SQLite
interview question bank**, and request screening questions. Continue with
comparison, explanation, or refinement requests.

## Regenerate the narrated video on Windows

The generator uses installed Microsoft PowerPoint and Windows text-to-speech;
it does not require Python packages:

```powershell
.\demos\create_mcp_demo.ps1
```

It creates an MP4 and an editable PowerPoint in `demos/`.

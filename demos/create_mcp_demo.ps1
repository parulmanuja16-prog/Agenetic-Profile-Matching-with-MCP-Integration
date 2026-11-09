$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputVideo = Join-Path $PSScriptRoot "mcp_end_to_end_demo.mp4"
$outputDeck = Join-Path $PSScriptRoot "mcp_end_to_end_demo.pptx"
$audioDirectory = Join-Path $env:TEMP ("mcp-demo-audio-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $audioDirectory | Out-Null

Add-Type -AssemblyName System.Speech

$slides = @(
    @{
        Title = "Agentic Profile Matching"
        Eyebrow = "MCP INTEGRATION · END-TO-END WALKTHROUGH"
        LeftHeading = "What this demo covers"
        LeftLines = @(
            "A resume-matching agent powered by a LangGraph workflow",
            "A filesystem MCP server for resume discovery and extraction",
            "A second SQLite MCP server for interview-question resources",
            "A Streamlit interface for search, batch processing, and watching"
        )
        RightHeading = "The key idea"
        RightLines = @(
            "The agent owns matching and decisions.",
            "MCP servers expose data and capabilities through a standard protocol.",
            "Both servers use Streamable HTTP and JSON-RPC 2.0."
        )
        Narration = "Welcome to this end-to-end walkthrough of the agentic profile matching project. In about five and a half minutes, we will follow a resume search from the Streamlit interface through the agent and filesystem MCP server, then see the second SQLite MCP server contribute interview questions. We will also cover batch processing, directory watching, follow-up conversations, and the commands needed to run the application. This is a narrated workflow visualization built from the project implementation, rather than a live screen capture. The two MCP servers are separate processes: one safely provides resume files, and the other provides a small skill-indexed interview question bank."
    },
    @{
        Title = "Two MCP servers, one agent"
        Eyebrow = "01 · ARCHITECTURE"
        LeftHeading = "Resume filesystem · port 8000"
        LeftLines = @(
            "Resources: filesystem://config and filesystem://resumes",
            "Resource template: filesystem://resumes/{filename}",
            "Tools: list, read, write, search, batch_process, watch_directory",
            "Every path is confined to the configured resume directory"
        )
        RightHeading = "Interview question bank · port 8001"
        RightLines = @(
            "SQLite-backed MCP resource provider",
            "interview-db://skills lists supported skills and counts",
            "interview-db://question-bank provides questions by skill",
            "Used for screening-question requests when enabled in Streamlit"
        )
        Narration = "The architecture has three main parts. Streamlit presents the chat and resume-management controls. The matching agent extracts role requirements, retrieves resumes, ranks candidates, and formats reports. The first MCP server is the filesystem boundary: by default it runs at localhost port 8000, provides configuration and resume resources, and offers tools including batch processing and watching. It resolves requested paths under the configured resume root. The optional interview-question server runs at localhost port 8001. It exposes two SQLite-backed resources: one catalogs available skills, and the other returns questions. The agent connects to this server only for screening questions when the Streamlit option is enabled."
    },
    @{
        Title = "Start both MCP servers"
        Eyebrow = "02 · SERVER SETUP"
        LeftHeading = "Terminal 1 · resume filesystem"
        LeftLines = @(
            "python filesystem_mcp_server.py",
            "Default endpoint: http://127.0.0.1:8000/mcp",
            "Set RESUME_DIRECTORY to use another resume folder",
            "Resources and tools are registered with FastMCP"
        )
        RightHeading = "Terminal 2 · interview database"
        RightLines = @(
            "python interview_mcp_server.py",
            "Default endpoint: http://127.0.0.1:8001/mcp",
            "Set INTERVIEW_MCP_SERVER_URL in the UI process to override",
            "The question bank is initialized in SQLite at startup"
        )
        Narration = "To run the demonstration, open two terminals in the project root and activate the project's Python environment. In the first terminal, run python filesystem_mcp_server.py. The default Streamable HTTP endpoint is localhost port 8000 with the MCP path. If your resumes live elsewhere, set RESUME_DIRECTORY before starting that server. In the second terminal, run python interview_mcp_server.py. It defaults to port 8001 and initializes its SQLite question bank when it starts. Keep both terminals open. The Streamlit process needs to use the same resume-directory configuration as the filesystem server, and can set INTERVIEW_MCP_SERVER_URL if the second server uses a different address."
    },
    @{
        Title = "MCP discovery and resume operations"
        Eyebrow = "03 · RESOURCES AND TOOLS"
        LeftHeading = "Protocol handshake"
        LeftLines = @(
            "Client initializes an MCP session",
            "Filesystem client discovers resources and templates",
            "Tool calls return structured results or explicit errors",
            "Resource reads expose configuration, catalog, and resume text"
        )
        RightHeading = "Streamlit sidebar"
        RightLines = @(
            "Batch process resumes calls batch_process",
            "Per-file read errors remain visible in the results",
            "Watch for new resumes calls watch_directory",
            "Interval and timeout are configurable and bounded"
        )
        Narration = "The clients use the MCP SDK rather than constructing protocol messages by hand. They initialize a session, discover the resources they need, and then read a resource or call a tool. The filesystem client also asks for resource templates. In Streamlit, the sidebar provides two explicit operations. Batch process resumes invokes batch_process, which reads supported files concurrently and returns successful files alongside individual errors. Watch for new resumes invokes watch_directory with a configurable polling interval and timeout. The watcher reports supported files added after the server process started. It does not automatically trigger a search or rebuild the vector index. These sidebar actions are separate from the batch read that the agent performs when it searches."
    },
    @{
        Title = "End-to-end agent search"
        Eyebrow = "04 · FROM PROMPT TO SHORTLIST"
        LeftHeading = "User request"
        LeftLines = @(
            "Find candidates with Python and 3+ years experience",
            "Streamlit sends the message with current conversation state",
            "The workflow extracts required skills and experience",
            "Search reads resume files through filesystem MCP"
        )
        RightHeading = "Agent response"
        RightLines = @(
            "Exact skill matching for recognized technology queries",
            "Otherwise: ChromaDB semantic search if the index is populated",
            "Otherwise: local lexical fallback",
            "Rank, deduplicate, explain, and retain the shortlist"
        )
        Narration = "Now follow a representative end-to-end request: find candidates with Python and three or more years of experience. Streamlit passes that message and the browser session's existing agent state to the matching agent. A new search enters the LangGraph workflow. The workflow parses the request, extracts skills and the experience threshold, then searches current resume files through the filesystem MCP client and batch_process tool. Recognized technology searches use exact term boundaries, so Python is matched as a skill rather than as an arbitrary substring. For other queries, the project uses ChromaDB semantic search when a populated index is available, or local lexical search when it is empty. The agent ranks and deduplicates candidates, builds an evidence-based initial report, and retains the criteria, candidate pool, and shortlist for follow-up messages."
    },
    @{
        Title = "A second server adds interview knowledge"
        Eyebrow = "05 · MULTI-MCP INTEGRATION"
        LeftHeading = "In Streamlit"
        LeftLines = @(
            "Enable Use SQLite interview question bank",
            "Ask: Create screening questions",
            "The matching agent keeps its role criteria and shortlist",
            "The interview MCP server is queried for this request"
        )
        RightHeading = "Two resources read"
        RightLines = @(
            "interview-db://skills catalogs the available topics",
            "interview-db://question-bank returns skill-indexed questions",
            "Questions for matching skills and general topics are selected",
            "The report combines agent-generated and database questions"
        )
        Narration = "The second server becomes visible in the screening-question flow. In the Streamlit sidebar, enable Use SQLite interview question bank and make a search so the conversation has active role criteria. Then ask, create screening questions. The agent first creates role-focused questions from the job description and extracted criteria. When the option is enabled, it initializes the second MCP session, discovers both interview resources, and reads the skills catalog and question bank. It filters the question bank to the role's required and preferred skills, and includes general questions. The final report combines these with the questions generated by the agent. If the optional server is not enabled, the existing screening-question behavior remains available without it."
    },
    @{
        Title = "Follow-ups and final workflow"
        Eyebrow = "06 · CONVERSATION AND VALIDATION"
        LeftHeading = "Continue the conversation"
        LeftLines = @(
            "Compare the top candidates side by side",
            "Ask why one candidate ranked above another",
            "Refine criteria and review ranking changes",
            "Request deep analysis, then final hire/no-hire decisions"
        )
        RightHeading = "Run and verify"
        RightLines = @(
            "python -m streamlit run ui\\streamlit_app.py",
            "Run filesystem MCP tests and interview MCP tests",
            "Start both servers before exercising MCP-backed actions",
            "Resume files and candidate decisions remain evidence-based"
        )
        Narration = "The conversation can continue with compare the top candidates, ask why one ranked higher, or refine requirements. Refinement updates the active criteria, reruns retrieval and ranking, and explains changes against the previous shortlist. The user can also request second-round analysis and final hire or no-hire decisions. From the project root, launch Streamlit with the command shown on screen, then open the local address it prints. For an integration check, run the focused filesystem MCP and interview MCP test modules. They verify resource and tool discovery, batch and watch behavior, and reading the second server's resources. This completes the demonstration: one agent uses resume data from the filesystem MCP server and, when selected, interview knowledge from the SQLite MCP server. Thank you for watching."
    }
)

function Add-TextBox {
    param(
        $Slide,
        [string]$Text,
        [single]$Left,
        [single]$Top,
        [single]$Width,
        [single]$Height,
        [single]$FontSize,
        [string]$Color,
        [bool]$Bold = $false
    )
    $shape = $Slide.Shapes.AddTextbox(1, $Left, $Top, $Width, $Height)
    $shape.TextFrame.MarginLeft = 0
    $shape.TextFrame.MarginRight = 0
    $shape.TextFrame.MarginTop = 0
    $shape.TextFrame.MarginBottom = 0
    $shape.TextFrame.WordWrap = -1
    $range = $shape.TextFrame.TextRange
    $range.Text = $Text
    $range.Font.Name = "Aptos"
    $range.Font.Size = $FontSize
    $range.Font.Bold = [int]$Bold
    $range.Font.Color.RGB = [int]$Color
    return $shape
}

function Add-Panel {
    param(
        $Slide,
        [single]$Left,
        [string]$Heading,
        [string[]]$Lines
    )
    $panel = $Slide.Shapes.AddShape(5, $Left, 142, 424, 298)
    $panel.Fill.ForeColor.RGB = 0x18263A
    $panel.Line.ForeColor.RGB = 0x2A3B53
    Add-TextBox $Slide $Heading ($Left + 22) 160 380 36 18 "0x6CE5C2" $true | Out-Null
    $body = ($Lines | ForEach-Object { "•  $_" }) -join "`r"
    $text = Add-TextBox $Slide $body ($Left + 22) 208 378 218 16 "0xF2F5FA"
    $text.TextFrame.TextRange.ParagraphFormat.SpaceAfter = 13
}

$powerPoint = $null
$presentation = $null
try {
    $synthesizer = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $synthesizer.Rate = -1
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $powerPoint.Visible = -1
    $presentation = $powerPoint.Presentations.Add()
    $presentation.PageSetup.SlideWidth = 960
    $presentation.PageSetup.SlideHeight = 540

    $index = 0
    foreach ($item in $slides) {
        $index++
        $slide = $presentation.Slides.Add($index, 12)
        $slide.Background.Fill.ForeColor.RGB = 0x101923

        $bar = $slide.Shapes.AddShape(1, 0, 0, 960, 8)
        $bar.Fill.ForeColor.RGB = 0x42D6B2
        $bar.Line.Visible = 0

        Add-TextBox $slide $item.Eyebrow 52 38 850 22 11 "0x42D6B2" $true | Out-Null
        Add-TextBox $slide $item.Title 52 67 850 56 30 "0xF2F5FA" $true | Out-Null

        if ($index -eq 1) {
            Add-TextBox $slide "A narrated walkthrough of the agent, Streamlit, and two MCP servers" 54 124 840 34 15 "0xAFC0D3" $false | Out-Null
            Add-Panel $slide 52 $item.LeftHeading $item.LeftLines
            Add-Panel $slide 484 $item.RightHeading $item.RightLines
        } else {
            Add-Panel $slide 52 $item.LeftHeading $item.LeftLines
            Add-Panel $slide 484 $item.RightHeading $item.RightLines
        }

        Add-TextBox $slide "AGENTIC PROFILE MATCHING  ·  MCP WORKFLOW" 52 478 760 22 10 "0x8293A8" $false | Out-Null
        Add-TextBox $slide ("{0:00} / {1:00}" -f $index, $slides.Count) 850 478 58 22 10 "0x8293A8" $false | Out-Null

        $audioPath = Join-Path $audioDirectory ("narration-{0:00}.wav" -f $index)
        $synthesizer.SetOutputToWaveFile($audioPath)
        $synthesizer.Speak($item.Narration)
        $synthesizer.SetOutputToDefaultAudioDevice()

        $audio = $slide.Shapes.AddMediaObject2($audioPath, 0, -1, 900, 500, 1, 1)
        $audio.AnimationSettings.PlaySettings.PlayOnEntry = -1
        $audio.AnimationSettings.PlaySettings.HideWhileNotPlaying = -1

        $reader = [System.IO.BinaryReader]::new(
            [System.IO.File]::OpenRead($audioPath)
        )
        try {
            $reader.BaseStream.Seek(28, [System.IO.SeekOrigin]::Begin) | Out-Null
            $bytesPerSecond = $reader.ReadUInt32()
        }
        finally {
            $reader.Dispose()
        }
        $audioDuration = (Get-Item -LiteralPath $audioPath).Length / $bytesPerSecond

        $transition = $slide.SlideShowTransition
        $transition.AdvanceOnClick = 0
        $transition.AdvanceOnTime = -1
        $transition.AdvanceTime = $audioDuration + 10
    }

    $presentation.SaveAs($outputDeck, 24)
    $presentation.CreateVideo($outputVideo, -1, 5, 720, 30, 85)
    while ($presentation.CreateVideoStatus -eq 1) {
        Start-Sleep -Seconds 3
    }
    if ($presentation.CreateVideoStatus -ne 3) {
        throw "PowerPoint video export failed with status $($presentation.CreateVideoStatus)."
    }
    Write-Output "Video: $outputVideo"
    Write-Output "Editable slides: $outputDeck"
}
finally {
    if ($presentation) {
        $presentation.Close()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($presentation)
    }
    if ($powerPoint) {
        $powerPoint.Quit()
        [void][Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint)
    }
    if ($synthesizer) {
        $synthesizer.Dispose()
    }
    Remove-Item -LiteralPath $audioDirectory -Recurse -Force -ErrorAction SilentlyContinue
}

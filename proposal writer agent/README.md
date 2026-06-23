# Nafezly Proposal Writer Agent

This agent opens a Nafezly project page, extracts the project description, and uses Groq to write a freelance proposal.

Shared settings live in the main project config file:

`E:\NIOx Team\Freelancing Job Applier\config.py`

Before running, set your Groq API key:

```powershell
$env:GROQ_API_KEY = "your_groq_api_key"
```

Run:

```powershell
& 'C:\Users\pc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'E:\NIOx Team\Freelancing Job Applier\proposal writer agent\write_proposal.py' 'https://nafezly.com/project/50630-landing-page'
```

The generated proposal is printed in the terminal and saved in `generated proposals`.

# Nafezly Job Collection Agent

This folder contains the code needed to run the Nafezly job collection agent.

Shared settings live in the main project config file:

`E:\NIOx Team\Freelancing Job Applier\config.py`

The agent:

- Logs into `nafezly.com`.
- Opens the projects page.
- Applies the development filter.
- Scrapes project cards with BeautifulSoup.
- Keeps only projects where `project_state` is open.
- Appends new projects to the configured CSV file.

Run it with:

```powershell
& 'C:\Users\pc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'E:\NIOx Team\Freelancing Job Applier\job collection agent\scrape_projects_to_csv.py'
```


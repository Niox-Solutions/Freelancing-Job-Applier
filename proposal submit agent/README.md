# Nafezly Proposal Submit Agent

This agent takes the output from the proposal writer agent and fills the Nafezly offer form:

- `period`
- `cost`
- `offer_description`

Shared settings live in:

`E:\NIOx Team\Freelancing Job Applier\config.py`

Dry run, fills the form but does not submit:

```powershell
& 'C:\Users\pc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'E:\NIOx Team\Freelancing Job Applier\proposal submit agent\write_and_submit_proposal.py' 'https://nafezly.com/project/50630-landing-page'
```

Real submit:

```powershell
& 'C:\Users\pc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'E:\NIOx Team\Freelancing Job Applier\proposal submit agent\write_and_submit_proposal.py' 'https://nafezly.com/project/50630-landing-page' --submit
```

The full pipeline signs in once and shares that authenticated browser session
with the collection, writer, and submit agents.

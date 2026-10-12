# TestForge

Turns plain-text Jira tickets into runnable pytest and Robot Framework test
suites using a local LLM (Ollama). It reads the ticket, pulls the source code it
needs to test, generates the tests, runs them for real, summarizes the logs, and
writes a report back to Confluence. Jira, Bitbucket and Confluence are all reached
through an MCP server.

Everything runs offline against mock Atlassian data, so you can clone it and try
it without any accounts.

```
Jira (MCP) --> Bitbucket (MCP) --> local LLM --> pytest + robot files
  ticket           source                             |
                                                    run tests
                                                       |
   Confluence (MCP) <-- analyze logs <-- real pass/fail results
      report
```

## The tests run against real code

The repo ships a small module to test, [sut/provisioning.py](sut/provisioning.py).
Each Jira ticket describes what one of its functions should do, Bitbucket serves
the source, and the generated tests run against it directly. The pass/fail counts
reflect an actual test run rather than the model's own claim.

## What a run does

`python cli.py run MXL-101` goes through five steps:

1. Fetch the Jira ticket (`get_jira_issue`) - description, acceptance criteria and
   a Mermaid flowchart.
2. Fetch the source under test from Bitbucket (`get_bitbucket_file`).
3. Ask the local LLM to write a pytest file and a `.robot` file, run each, and
   fix any file that won't execute.
4. Ask the LLM for a short plain-English summary of the logs.
5. Publish the report to Confluence (`publish_confluence_page`) and save a copy.

Steps 1, 2 and 5 go through the MCP server, so the workflow never touches the
data store directly.

## Setup

You need Python 3.10+ and [Ollama](https://ollama.com) running locally.

```bash
# qwen2.5-coder:7b gives reliable results; 3b is a lighter fallback
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:3b        # optional

pip install -r requirements.txt
```

The best installed model is picked automatically (see `PREFERRED_MODELS` in
[workflow/llm.py](workflow/llm.py)). To force one, set `OLLAMA_MODEL` in a `.env`
file (see [.env.example](.env.example)).

## Usage

```bash
python cli.py list                  # show the tickets that are ready to test
python cli.py run MXL-101           # full run for one ticket
python cli.py run MXL-102 --no-llm-summary   # skip the summary step (faster)
```

Generated tests land in `generated_tests/`, logs and parsed results in
`results/<KEY>/`, and the report in `results/<KEY>/report.md` plus the mock
Confluence store at `data/confluence/pages.json`.

## Sample tickets

| Key | Feature | Function |
| --- | --- | --- |
| `MXL-101` | IPv4 address validation | `validate_ipv4` |
| `MXL-102` | Bandwidth string parser | `parse_bandwidth` |
| `MXL-103` | MAC address normalization | `normalize_mac` |

With `qwen2.5-coder:7b` all three pass on both frameworks (pytest 8/8, 7/7, 6/6;
robot 7/7, 7/7, 6/6). To add your own, drop a JSON file in [data/jira/](data/jira/)
following the shape of an existing one and point `target_function` at code in
[sut/](sut/).

## Getting usable tests out of a small model

A local model will sometimes write malformed or wrong tests. A few things that
help:

- The model gets the function's signature and docstring (pulled out with `ast`)
  plus a small table of known input/output examples from the ticket, not the full
  implementation. It fills in the test structure instead of guessing expected
  values or copying the source back.
- Generated files are checked before use and rejected if they look broken: empty,
  a `pass` stub with no assertions, a leftover code fence, a repetition loop, a
  missing `import pytest`, or a robot file that redefines the library keyword. A
  rejected file is retried.
- If a file won't execute, the error is fed back to the model to fix it. Tests
  that run but fail are reported as-is, not rewritten until they pass, otherwise
  the tool would just hide bugs. (Set `REPAIR_ON_FAILURE=1` to change that.)
- Each run deletes the previous `output.xml` / junit before running, so a broken
  run can't accidentally report the last run's pass count.

Decoding runs at temperature 0 with a repetition penalty and an output cap, which
stops the runaway repetition small models tend to fall into.

## Tests

The workflow's own code (the quality gate, the pytest/Robot result parsers, the
mock store, the report builder) has a plain pytest suite under `tests/`, no
Ollama required:

```bash
pytest
```

`tests/` covers the plumbing around the model and the mutation checker described next. What the model
writes is measured separately, because a unit test cannot say whether generated tests are any good.

## How good are the generated tests?

"All tests pass" is weak evidence, because a test file with no useful assertions passes too. So `quality/` asks a
harder question. It seeds 28 deliberate bugs into `sut/provisioning.py` (a comparison off by one, a dropped check,
a wrong constant) and counts how many of them make the generated tests fail.

```bash
python -m quality.mutation_check     # uses generated_tests/, or examples/last_run/ if there is none
```

Result for the tests `qwen2.5-coder:7b` wrote in the last run, which are saved in [examples/last_run/](examples/last_run/):

| function | real bugs | caught by its own tests | missed |
|---|---|---|---|
| `validate_ipv4` | 7 | 4 (57%) | five parts accepted, non-digits accepted, non-string input |
| `parse_bandwidth` | 8 | 5 (62%) | zero rejected, rounding up, non-string input |
| `normalize_mac` | 7 | 6 (86%) | thirteen hex digits accepted |
| `provision_device` | 6 | 4 (67%) | bandwidth not validated, error list dropped |
| **all** | 28 | 19 (68%) | |

The model writes the cases the ticket's examples show and misses boundaries the docstring only states, such as
five-part addresses or zero bandwidth. So "pytest 8/8" was true and told you much less than it sounded.

What this does and does not show:

- The bugs are 28 that I wrote, in one small module. It measures this model on this code, not test generators in general.
- A bug only counts if it changes the function's answer on at least one probe input. One edit did nothing a caller
  could see (removing the empty-string check, because the next line raises the same error) and was left out.
- Only the pytest files are measured, not the Robot ones.
- The checker itself is tested both ways: a thorough hand-written suite in `tests/reference_suite/` catches every
  counted bug, and an empty suite catches none ([tests/test_mutation_check.py](tests/test_mutation_check.py)).

## Layout

```
cli.py                 the orchestrator (fetch -> generate -> run -> analyze -> publish)
sut/provisioning.py    the code the generated tests run against
quality/               seeded bugs and the mutation check that scores the generated tests
examples/last_run/     the tests the model wrote in the last run
data/jira/*.json       mock Jira tickets
data/confluence/       mock Confluence store
tests/                 unit tests for the workflow code, plus a hand-written reference suite
mcp_server/
  server.py            MCP server exposing the Jira/Bitbucket/Confluence tools
  mock_store.py        file-backed data behind those tools
workflow/
  llm.py               Ollama wrapper and model selection
  prompts.py           the generation and repair prompts
  generate.py          spec extraction, generation, the quality checks, repair
  run_tests.py         runs pytest + robot and parses the results
  analyze.py           log summary and report builder
  mcp_client.py        client that talks to the MCP server
```

## Pointing it at real Atlassian

Every call goes through MCP, so only [mcp_server/mock_store.py](mcp_server/mock_store.py)
would change: swap the file reads/writes for Atlassian REST calls. The tools and
the rest of the workflow stay the same.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Model calls hang | Make sure Ollama is running (`ollama list` should respond). |
| `model ... not found` | Pull the model, or set `OLLAMA_MODEL` to one you have. |
| Tests fail more with the 3b model | It's less reliable at this; use the 7b model. |
| Runs feel slow | It's local CPU inference; a GPU helps a lot. |
| `INFO ... server.py` lines in output | MCP server logging on stderr; ignore or filter with `2>NUL`. |

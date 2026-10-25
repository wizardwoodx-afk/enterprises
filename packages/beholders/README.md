# Beholders

The crew runtime embedded in Beyond. A **Beholders crew** is a team of
role-playing agents working through an ordered list of tasks; a **flow** is the
stateful orchestration around those crews.

```python
from beholders import Agent, Crew, Process, Task

researcher = Agent(role="Researcher", goal="Find primary sources", backstory="Patient.")
gather = Task(description="Collect evidence about {topic}.", agent=researcher, expected_output="A cited list.")

crew = Crew(agents=[researcher], tasks=[gather], process=Process.sequential)
print(crew.kickoff(inputs={"topic": "tidal power"}))
```

Beyond adds a thin service layer (`beholders.service`) that stores crews, runs
them off the UI thread, streams their lifecycle, and exposes them over three
doors — REST, JSON-RPC, and a stdlib HTTP adapter:

```console
$ beholders crews
$ beholders run crew_ab12 --inputs '{"topic": "tidal power"}'
$ beholders serve --port 8787
```

See `docs/BEHOLDERS.md` in the Beyond repository for the desktop integration,
and `LICENSE` for the upstream MIT terms this engine is derived from.

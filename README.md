# ForgeOps

26년도 개인 프로젝트

## Portable Agent Harness

ForgeOps는 프로젝트 독립적인 세 역할 agent harness protocol 2.0을 포함한다.

- Codex/프로젝트 지시: [AGENTS.md](AGENTS.md)
- Copilot adapter: [.github/copilot-instructions.md](.github/copilot-instructions.md)
- Main orchestrator: [.github/agents/main_instruction.prompt.md](.github/agents/main_instruction.prompt.md)
- Part analyst: [.github/agents/part_agent.prompt.md](.github/agents/part_agent.prompt.md)
- Work executor: [.github/agents/work_agent.prompt.md](.github/agents/work_agent.prompt.md)
- 적용 및 이식 가이드: [docs/agent-harness/PORTING_GUIDE.md](docs/agent-harness/PORTING_GUIDE.md)

다른 프로젝트에는 세 agent prompt를 그대로 복사하고, 대상 프로젝트의
adapter와 project_profile만 작성한다.
